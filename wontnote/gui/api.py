"""
api.py — WontNote PyWebView Javascript Bridge API
==================================================
Handles all calls from the HTML/JS frontend to the cryptographic engine,
vault storage, and note manager.
"""

from datetime import datetime, timezone
from copy import deepcopy
from functools import wraps
from threading import RLock
import time
import math

from wontnote.crypto_core import (
    VaultError,
    create_vault,
    unlock_with_password,
    unlock_with_recovery_key,
    save_notes,
    change_password,
    regenerate_recovery_key,
    _secure_zero,
    _unpack_vault,
)
from wontnote.vault_storage import read_vault, write_vault, write_new_vault, vault_path
from wontnote.notes import create_note as make_note
from wontnote.gui.preferences import read_preferences, save_preference


def synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._state_lock:
            return method(self, *args, **kwargs)
    return wrapped


def note_mutation(method):
    """Serialize vault changes and roll memory back if disk persistence fails."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._state_lock:
            if self._master_key is None or self._vault_bytes is None:
                return {"success": False, "error": "Vault is not open."}
            previous = deepcopy(self._notes)
            try:
                return method(self, *args, **kwargs)
            except Exception:
                self._notes = previous
                return {"success": False, "error": "Could not save note. Please try again."}
    return wrapped


class WontNoteAPI:
    """JS-accessible API exposed via window.pywebview.api."""

    def __init__(self):
        self._state_lock = RLock()
        self._allow_close = False
        self._failed_attempts = 0
        self._retry_after = 0.0
        self._clock = time.monotonic
        self._window = None
        self._vault_bytes: bytes | None = None
        self._master_key: bytearray | None = None
        self._notes: list[dict] = []

    def _set_window(self, window):
        self._window = window

    # ── State & Authentication ────────────────────────────────────────────────
    @synchronized
    def get_initial_state(self) -> dict:
        """Called on page load to determine whether to show Setup or Login."""
        try:
            self._vault_bytes = read_vault()
            has_vault = True
        except FileNotFoundError:
            self._vault_bytes = None
            has_vault = False

        return {
            "has_vault": has_vault,
            "unlocked": self._master_key is not None,
            "preferences": read_preferences(),
        }

    @synchronized
    def set_preference(self, key: str, value: str) -> dict:
        try:
            save_preference(key, value)
            return {"success": True}
        except Exception:
            return {"success": False, "error": "Could not save preference."}

    @synchronized
    def create_vault(self, password: str) -> dict:
        """Create a new vault with password (must be >= 12 characters)."""
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            return {"success": False, "error": "Password must be 12–1024 characters."}
        try:
            read_vault()
        except FileNotFoundError:
            pass
        except Exception:
            return {"success": False, "error": "Vault state could not be verified; existing data is preserved."}
        else:
            return {"success": False, "error": "A vault already exists. Unlock it first."}

        try:
            vault_bytes, recovery_key = create_vault(password)
            write_new_vault(vault_bytes)
            self._vault_bytes = vault_bytes

            # Auto unlock after creation
            mk, notes = unlock_with_password(vault_bytes, password)
            self._master_key = mk
            self._notes = notes

            return {
                "success": True,
                "recovery_key": recovery_key,
                "notes": self._notes,
            }
        except Exception as exc:
            return {"success": False, "error": f"Could not create vault: {exc}"}

    @synchronized
    def unlock_password(self, password: str) -> dict:
        """Unlock the vault using password."""
        blocked = self._auth_blocked()
        if blocked:
            return blocked
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            return self._auth_failed()
        if self._master_key is not None:
            return {"success": False, "error": "Vault is already open."}
        if not self._vault_bytes:
            try:
                self._vault_bytes = read_vault()
            except Exception:
                return {"success": False, "error": "Vault file not found."}

        try:
            fields = _unpack_vault(self._vault_bytes)
            if fields["memory_cost"] > 262144 or fields["time_cost"] > 6 or fields["parallelism"] > 8:
                return {"success": False, "error": "Vault exceeds safe resource limits."}
            mk, notes = unlock_with_password(self._vault_bytes, password)
            self._master_key = mk
            self._notes = notes
            self._failed_attempts = 0
            self._retry_after = 0.0
            return {"success": True, "notes": deepcopy(self._notes)}
        except VaultError:
            return self._auth_failed()
        except Exception:
            return {"success": False, "error": "Could not open vault."}

    @synchronized
    def unlock_recovery(self, recovery_key_str: str) -> dict:
        """Unlock the vault using recovery key."""
        blocked = self._auth_blocked()
        if blocked:
            return blocked
        if not isinstance(recovery_key_str, str) or len(recovery_key_str) > 256:
            return self._auth_failed()
        if self._master_key is not None:
            return {"success": False, "error": "Vault is already open."}
        if not self._vault_bytes:
            try:
                self._vault_bytes = read_vault()
            except Exception:
                return {"success": False, "error": "Vault file not found."}

        try:
            mk, notes = unlock_with_recovery_key(self._vault_bytes, recovery_key_str)
            self._master_key = mk
            self._notes = notes
            self._failed_attempts = 0
            self._retry_after = 0.0
            return {"success": True, "notes": deepcopy(self._notes)}
        except VaultError:
            return self._auth_failed()
        except Exception:
            return {"success": False, "error": "Could not open vault."}

    def _auth_blocked(self):
        remaining = math.ceil(self._retry_after - self._clock())
        if remaining > 0:
            return {"success": False, "retry_seconds": remaining,
                    "error": f"Too many failed attempts. Wait {remaining} seconds."}
        return None

    def _auth_failed(self):
        self._failed_attempts += 1
        if self._failed_attempts >= 5:
            self._retry_after = self._clock() + min(60, 5 * 2 ** min(self._failed_attempts - 5, 4))
        return {"success": False, "error": "Invalid password or recovery key."}

    def lock(self) -> dict:
        with self._state_lock:
            return self._lock()

    def _lock(self) -> dict:
        """Lock the vault: erase master key from memory, clear notes."""
        if self._master_key is not None:
            try:
                _secure_zero(self._master_key)
            except Exception:
                pass
            self._master_key = None

        for n in self._notes:
            n.clear()
        self._notes = []
        return {"success": True}

    # ── Notes Management ──────────────────────────────────────────────────────
    @synchronized
    def get_notes(self) -> list:
        return deepcopy(self._notes) if self._master_key is not None else []

    @note_mutation
    def create_note(self, folder: str = "Personal") -> dict:
        """Create a new note and immediately persist it."""
        if not isinstance(folder, str) or len(folder) > 100:
            return {"success": False, "error": "Invalid folder."}
        note = make_note("Untitled Note", "")
        note["folder"] = folder
        note["pinned"] = False
        note["deleted"] = False
        note["tags"] = []

        self._notes.insert(0, note)
        self._persist()
        return {"success": True, "note": note, "notes": self._notes}

    @note_mutation
    def save_note(self, note_data: dict) -> dict:
        """Update note fields and persist."""
        if not isinstance(note_data, dict):
            return {"success": False, "error": "Invalid note."}
        for field in ("title", "content", "folder", "font"):
            if field in note_data and not isinstance(note_data[field], str):
                return {"success": False, "error": "Invalid note field."}
        if len(note_data.get("content", "")) > 2_000_000 or len(note_data.get("title", "")) > 500:
            return {"success": False, "error": "Note size limit exceeded."}
        note_id = note_data.get("id")
        target = None
        for n in self._notes:
            if n.get("id") == note_id:
                target = n
                break

        now_iso = datetime.now(timezone.utc).isoformat()
        if target is not None:
            target["title"] = note_data.get("title", target.get("title", ""))
            target["content"] = note_data.get("content", target.get("content", ""))
            if "folder" in note_data:
                target["folder"] = note_data["folder"]
            if "pinned" in note_data:
                target["pinned"] = bool(note_data["pinned"])
            if "deleted" in note_data:
                target["deleted"] = bool(note_data["deleted"])
            if "tags" in note_data:
                target["tags"] = note_data["tags"]
            for field in ("paper", "attachments"):
                if field in note_data:
                    target[field] = deepcopy(note_data[field])
            if "font" in note_data:
                target["font"] = str(note_data["font"])
            if "font_size" in note_data:
                size = note_data["font_size"]
                target["font_size"] = size if size in (12,14,16,18,20,24,28,32) else 14
            target["modified"] = now_iso
            saved_note = target
        else:
            return {"success": False, "error": "Note not found."}

        self._persist()
        time_str = datetime.now().strftime("%H:%M")
        return {
            "success": True,
            "saved_at": time_str,
            "note": saved_note,
            "notes": self._notes,
        }

    @note_mutation
    def toggle_pin(self, note_id: str) -> dict:
        """Toggle pinned status for a note."""
        pinned = False
        for n in self._notes:
            if n.get("id") == note_id:
                n["pinned"] = not n.get("pinned", False)
                n["modified"] = datetime.now(timezone.utc).isoformat()
                pinned = n["pinned"]
                break
        self._persist()
        return {"success": True, "pinned": pinned, "notes": self._notes}

    @note_mutation
    def delete_note(self, note_id: str, permanent: bool = False) -> dict:
        """Move note to trash or permanently delete it."""
        if permanent:
            self._notes = [n for n in self._notes if n.get("id") != note_id]
        else:
            for n in self._notes:
                if n.get("id") == note_id:
                    n["deleted"] = True
                    n["modified"] = datetime.now(timezone.utc).isoformat()
                    break
        self._persist()
        return {"success": True, "notes": self._notes}

    @note_mutation
    def restore_note(self, note_id: str) -> dict:
        """Restore a note from trash."""
        for n in self._notes:
            if n.get("id") == note_id:
                n["deleted"] = False
                n["modified"] = datetime.now(timezone.utc).isoformat()
                break
        self._persist()
        return {"success": True, "notes": self._notes}

    # ── Security Settings ─────────────────────────────────────────────────────
    @note_mutation
    def change_password(self, cur_pwd: str, new_pwd: str) -> dict:
        """Verify current password and update vault to new password."""
        if not isinstance(new_pwd,str) or not 12 <= len(new_pwd) <= 1024:
            return {"success": False, "error": "New password must be 12–1024 characters."}
        if not isinstance(cur_pwd,str) or len(cur_pwd) > 1024:
            return {"success": False, "error": "Invalid current password."}

        try:
            temp_mk, _ = unlock_with_password(self._vault_bytes, cur_pwd)
        except VaultError:
            return {"success": False, "error": "Current password is incorrect."}

        try:
            new_vault = change_password(self._vault_bytes, temp_mk, new_pwd)
            write_vault(new_vault, keep_backup=False)
            self._vault_bytes = new_vault
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": f"Could not change password: {exc}"}
        finally:
            _secure_zero(temp_mk)

    @note_mutation
    def regenerate_recovery_key(self) -> dict:
        """Generate a fresh recovery key and re-encrypt recovery slot."""
        if self._master_key is None or self._vault_bytes is None:
            return {"success": False, "error": "Vault is not open."}

        try:
            new_vault, new_key = regenerate_recovery_key(
                self._vault_bytes, self._master_key
            )
            write_vault(new_vault, keep_backup=False)
            self._vault_bytes = new_vault
            return {"success": True, "recovery_key": new_key}
        except Exception as exc:
            return {"success": False, "error": f"Could not generate key: {exc}"}

    @synchronized
    def reset_vault(self, password: str = "", confirmation: str = "") -> dict:
        """Verify the current password and explicit confirmation before reset."""
        if (
            confirmation != "CONFIRM"
            or not isinstance(password, str)
            or not password
            or len(password) > 1024
        ):
            return {
                "success": False,
                "error": "Current password and confirmation are required.",
            }
        blocked = self._auth_blocked()
        if blocked:
            return blocked
        try:
            data = read_vault()
            fields = _unpack_vault(data)
            if (
                fields["memory_cost"] > 262144
                or fields["time_cost"] > 6
                or fields["parallelism"] > 8
            ):
                return {
                    "success": False,
                    "error": "Vault exceeds safe resource limits.",
                }
            key, _ = unlock_with_password(data, password)
        except Exception:
            return self._auth_failed()
        try:
            _secure_zero(key)
            p = vault_path()
            bak = p.parent / "vault.wnt.bak"
            bak.unlink(missing_ok=True)
            p.unlink()
            self._lock()
            self._vault_bytes = None
            return {"success": True}
        except Exception:
            return {"success": False, "error": "Could not reset vault."}

    # ── Window Controls (Safe fallbacks) ───────────────────────────────────────
    def minimize(self) -> dict:
        if self._window:
            try:
                self._window.minimize()
            except Exception:
                pass
        return {"success": True}

    def toggle_maximize(self) -> dict:
        if self._window:
            try:
                if getattr(self._window, "is_maximized", False):
                    self._window.restore()
                else:
                    self._window.maximize()
            except Exception:
                pass
        return {"success": True}

    def close(self) -> dict:
        self._allow_close = True
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        return {"success": True}

    # ── Persistence Helper ────────────────────────────────────────────────────
    def _persist(self):
        if self._master_key is not None and self._vault_bytes is not None:
            new_vault = save_notes(self._vault_bytes, self._master_key, self._notes)
            write_vault(new_vault)
            self._vault_bytes = new_vault
