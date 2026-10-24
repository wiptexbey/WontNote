"""
vault_storage.py — WontNote Secure Vault File Manager
======================================================
Locates and stores the vault file in the platform-appropriate user data
directory via platformdirs.

Safe Write Strategy:
    1. Create a temporary file in the *same* directory as the target
       (guarantees the same filesystem — required for atomic rename).
    2. Write vault bytes.
    3. flush() + os.fsync() — flush OS buffers to disk.
    4. On Linux, set file permissions to 0o600 and directory to 0o700.
    5. Before replacing an existing vault, copy it to vault.wnt.bak in the same directory.
    6. os.replace() — atomically overwrite the target (with retry on Windows PermissionError).
    7. On Linux/POSIX, fsync the parent directory after os.replace.
    8. Any failure cleans up the temporary .tmp file.

No plaintext backups or leftover temporary copies are ever created.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

from platformdirs import user_data_dir

# Application identifiers used by platformdirs
APP_NAME   = "WontNote"
APP_AUTHOR = "WontNote"

# Vault filename
VAULT_FILENAME = "vault.wnt"
BACKUP_FILENAME = "vault.wnt.bak"


def vault_dir(custom_dir: Path | str | None = None) -> Path:
    """
    Return the platform-appropriate user data directory for WontNote.

    Windows: C:\\Users\\<user>\\AppData\\Local\\WontNote
    Linux:   ~/.local/share/WontNote

    Creates the directory if it does not exist with mode 0o700.
    On Linux/POSIX, chmod 0o700 is applied ONLY if this code created the directory.
    """
    if custom_dir is not None:
        directory = Path(custom_dir)
    else:
        directory = Path(user_data_dir(APP_NAME, appauthor=False))

    dir_existed = directory.exists()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Restrict access on Linux: only the owner can read/write/enter, and only if newly created
    if sys.platform != "win32" and not dir_existed:
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass

    return directory


def vault_path(
    custom_path: Path | str | None = None,
    custom_dir: Path | str | None = None,
) -> Path:
    """Return the full path to the vault file."""
    if custom_path is not None:
        return Path(custom_path)
    return vault_dir(custom_dir) / VAULT_FILENAME


def vault_exists(path: Path | str | None = None) -> bool:
    """Return True if the vault file is present on disk."""
    return vault_path(custom_path=path).exists()


def read_vault(path: Path | str | None = None) -> bytes:
    """
    Read the vault file and return its raw bytes.

    Raises:
        FileNotFoundError: Vault file does not exist.
        IOError: Read error.
    """
    p = vault_path(custom_path=path)
    if not p.exists():
        raise FileNotFoundError("Vault file not found.")
    return p.read_bytes()


def _safe_replace(src: Path, dst: Path, max_retries: int = 5, retry_delay: float = 0.05) -> None:
    """
    Atomically replace dst with src. On Windows, if a temporary PermissionError
    occurs (e.g. file lock or indexing), retry up to max_retries before raising.
    """
    for attempt in range(max_retries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if sys.platform == "win32" and attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise


def _atomic_write_file(target_path: Path, data: bytes) -> None:
    """
    Safely write data to target_path using a temporary file in the same directory.
    All write steps are wrapped in try/except/finally to ensure temp file cleanup on failure.
    """
    directory = target_path.parent
    dir_existed = directory.exists()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if sys.platform != "win32" and not dir_existed:
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass

    tmp_path = None
    try:
        tmp_fd, tmp_path_str = tempfile.mkstemp(dir=directory, suffix=".tmp")
        tmp_path = Path(tmp_path_str)

        with os.fdopen(tmp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if sys.platform != "win32":
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass

        _safe_replace(tmp_path, target_path)
        tmp_path = None  # Replaced successfully

        # On Linux/POSIX, fsync the containing directory
        if sys.platform != "win32":
            try:
                dir_fd = os.open(str(directory), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    except Exception:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        raise
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


def write_vault(
    vault_bytes: bytes,
    path: Path | str | None = None,
    keep_backup: bool = True,
) -> None:
    """
    Save vault bytes to disk using a safe atomic write.

    Parameters:
        vault_bytes: Encrypted vault blob to store.
        path: Optional path to vault file (defaults to standard platformdirs location).
        keep_backup: Whether to create a backup file before writing.
            Callers such as change_password and regenerate_recovery_key must pass
            keep_backup=False, because the backup would otherwise still open with
            the old password or old recovery key. When keep_backup=False, no new
            vault.wnt.bak is created, and after the new vault is written successfully,
            any existing vault.wnt.bak is deleted (ignoring deletion errors).

    Steps:
        - If keep_backup=True and an existing vault exists at the target location,
          back it up to vault.wnt.bak in the same directory (safely written, mode 0o600 on Linux).
        - Write to a temporary file in the same directory (same filesystem).
        - flush() + fsync() to ensure data reaches disk.
        - On Linux, set file permissions to 0o600.
        - os.replace() for an atomic rename over the target (with retries on Windows).
        - On Linux, fsync the containing directory.
        - If keep_backup=False, delete any existing vault.wnt.bak.

    Raises:
        IOError: Write error.
    """
    target_path = vault_path(custom_path=path)
    directory = target_path.parent
    bak_path = directory / BACKUP_FILENAME

    # Backup existing vault before overwriting if keep_backup is True
    if keep_backup and target_path.exists():
        existing_bytes = target_path.read_bytes()
        _atomic_write_file(bak_path, existing_bytes)

    # Atomic write to target vault file
    _atomic_write_file(target_path, vault_bytes)

    # If keep_backup is False, remove any existing backup after successful write
    if not keep_backup:
        try:
            bak_path.unlink(missing_ok=True)
        except OSError:
            pass


def write_new_vault(vault_bytes: bytes, path: Path | str | None = None) -> None:
    """Publish a complete new vault atomically, never replacing an existing one.

    The hard link creation is exclusive across processes; a check-then-replace
    would let two setup windows overwrite one another.
    """
    target = vault_path(custom_path=path)
    directory = target.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=directory, suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(vault_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def delete_vault(path: Path | str | None = None) -> None:
    """
    Delete the vault file (and backup if present) from disk.
    Only used in tests or when the user explicitly resets the vault.
    """
    p = vault_path(custom_path=path)
    if p.exists():
        p.unlink()
    bak = p.parent / BACKUP_FILENAME
    if bak.exists():
        bak.unlink()
