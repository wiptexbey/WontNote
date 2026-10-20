"""
test_crypto_core.py — WontNote Encryption Core Test Suite
==========================================================
Covered scenarios:
     1.  Open vault with the correct password
     2.  Reject wrong password (VaultError)
     3.  Open vault with recovery key
     4.  Change password: old password must no longer work; notes preserved
     5.  Regenerate recovery key: old key must no longer work
     6.  Corrupted file — flip one byte in the header
     7.  Corrupted file — flip one byte in the encrypted notes block
     8.  Unknown format version
     9.  Invalid magic bytes
    10.  Short password rejected at vault creation
    11.  Short password rejected when changing password
    12.  Different nonce produced on every save
    13.  Atomic write error simulation (vault_storage)
    14.  Argon2id parameter upper-bound enforcement
    15.  Save and reload notes (data integrity)
    16.  create_note and update_note helpers
    17.  Invalid recovery key format
    18.  Correct format but wrong recovery key
    19.  _secure_zero zeroes a bytearray
"""

import os
import struct
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wontnote.crypto_core import (
    VaultError,
    MAGIC_BYTES,
    FORMAT_VERSION,
    DEFAULT_MEMORY_COST,
    DEFAULT_TIME_COST,
    DEFAULT_PARALLELISM,
    MEMORY_COST_MAX,
    TIME_COST_MAX,
    PARALLELISM_MAX,
    MIN_PASSWORD_LENGTH,
    create_vault,
    unlock_with_password,
    unlock_with_recovery_key,
    save_notes,
    change_password,
    regenerate_recovery_key,
    create_note,
    update_note,
    _secure_zero,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

VALID_PASSWORD   = "StrongPassword123!"   # 18 chars — valid
VALID_PASSWORD_2 = "NewPassword456@!"     # 16 chars — valid


def make_vault(password: str = VALID_PASSWORD) -> tuple[bytes, str]:
    """Create a fresh vault and return (vault_bytes, recovery_key_str)."""
    return create_vault(password)


# ---------------------------------------------------------------------------
# 1. Open vault with correct password
# ---------------------------------------------------------------------------

def test_open_with_correct_password():
    """A correct password should open the vault and return an empty note list."""
    vault, _ = make_vault()
    master_key, notes = unlock_with_password(vault, VALID_PASSWORD)
    assert isinstance(notes, list)
    assert len(notes) == 0
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 2. Reject wrong password
# ---------------------------------------------------------------------------

def test_wrong_password_raises():
    """A wrong password must raise VaultError."""
    vault, _ = make_vault()
    with pytest.raises(VaultError):
        unlock_with_password(vault, "WrongPassword999!")


# ---------------------------------------------------------------------------
# 3. Open vault with recovery key
# ---------------------------------------------------------------------------

def test_open_with_recovery_key():
    """The recovery key must open the vault successfully."""
    vault, recovery_str = make_vault()
    master_key, notes = unlock_with_recovery_key(vault, recovery_str)
    assert isinstance(notes, list)
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 4. Change password
# ---------------------------------------------------------------------------

def test_change_password():
    """
    After changing the password:
    - The old password must no longer work.
    - The new password must work.
    - Notes must be preserved.
    """
    vault, _ = make_vault()

    # Add a note
    master_key, notes = unlock_with_password(vault, VALID_PASSWORD)
    notes.append(create_note("Title", "Content"))
    vault = save_notes(vault, master_key, notes)
    _secure_zero(master_key)

    # Change password
    master_key, _ = unlock_with_password(vault, VALID_PASSWORD)
    vault = change_password(vault, master_key, VALID_PASSWORD_2)
    _secure_zero(master_key)

    # Old password must not work
    with pytest.raises(VaultError):
        unlock_with_password(vault, VALID_PASSWORD)

    # New password must work and notes must be intact
    master_key, recovered_notes = unlock_with_password(vault, VALID_PASSWORD_2)
    assert len(recovered_notes) == 1
    assert recovered_notes[0]["title"] == "Title"
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 5. Regenerate recovery key
# ---------------------------------------------------------------------------

def test_regenerate_recovery_key():
    """
    After regenerating the recovery key:
    - The old recovery key must no longer work.
    - The new recovery key must work.
    """
    vault, old_recovery = make_vault()
    master_key, _ = unlock_with_password(vault, VALID_PASSWORD)
    vault, new_recovery = regenerate_recovery_key(vault, master_key)
    _secure_zero(master_key)

    # Old key must not work
    with pytest.raises(VaultError):
        unlock_with_recovery_key(vault, old_recovery)

    # New key must work
    master_key, notes = unlock_with_recovery_key(vault, new_recovery)
    assert isinstance(notes, list)
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 6. Corrupted file — header byte flipped
# ---------------------------------------------------------------------------

def test_corrupted_header():
    """Flipping a byte in the header must cause authentication to fail."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    # Position 10 is the parallelism byte (inside the KDF parameters region)
    corrupted[10] ^= 0xFF
    with pytest.raises((VaultError, ValueError)):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 7. Corrupted file — notes block byte flipped
# ---------------------------------------------------------------------------

def test_corrupted_notes_block():
    """Flipping a byte in the encrypted notes block must cause authentication to fail."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[-1] ^= 0xFF  # Flip the last byte of the GCM tag
    with pytest.raises((VaultError, ValueError)):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 8. Unknown format version
# ---------------------------------------------------------------------------

def test_unknown_format_version():
    """A version byte other than 0x01 must raise ValueError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[4] = 0x99   # Version byte is at position 4
    with pytest.raises(ValueError, match="Unsupported format version"):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 9. Invalid magic bytes
# ---------------------------------------------------------------------------

def test_invalid_magic_bytes():
    """Magic bytes that do not match must raise ValueError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[0:4] = b"XXXX"
    with pytest.raises(ValueError, match="magic bytes"):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 10. Short password rejected at vault creation
# ---------------------------------------------------------------------------

def test_short_password_at_creation():
    """A password shorter than 12 characters must be rejected at creation."""
    with pytest.raises(ValueError, match="at least"):
        create_vault("Short1234!")   # 10 characters


# ---------------------------------------------------------------------------
# 11. Short password rejected when changing password
# ---------------------------------------------------------------------------

def test_short_password_at_change():
    """A password shorter than 12 characters must be rejected when changing."""
    vault, _ = make_vault()
    master_key, _ = unlock_with_password(vault, VALID_PASSWORD)
    with pytest.raises(ValueError, match="at least"):
        change_password(vault, master_key, "Short1234!")   # 10 characters
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 12. Different nonce on every save
# ---------------------------------------------------------------------------

def test_different_nonce_each_save():
    """
    Saving the same notes twice must produce different ciphertexts because
    a fresh nonce is generated each time.
    """
    vault, _ = make_vault()
    master_key, notes = unlock_with_password(vault, VALID_PASSWORD)

    vault_v1 = save_notes(vault, master_key, notes)
    vault_v2 = save_notes(vault, master_key, notes)

    # Different nonces → different ciphertexts
    assert vault_v1 != vault_v2
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 13. Atomic write error simulation
# ---------------------------------------------------------------------------

def test_atomic_write_error_simulation():
    """
    If writing to the temporary file fails, the existing vault file must
    remain intact and no leftover .tmp file should be present.
    """
    from wontnote import vault_storage

    vault, _ = make_vault()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        with patch.object(vault_storage, "vault_dir", return_value=tmp_dir_path), \
             patch.object(vault_storage, "vault_path",
                          return_value=tmp_dir_path / "vault.wnt"):

            # First successful write
            vault_storage.write_vault(vault)
            original_content = vault_storage.read_vault()

            # Simulate a disk write error
            original_fdopen = os.fdopen

            def failing_fdopen(fd, mode):
                f = original_fdopen(fd, mode)

                class FailingFile:
                    def write(self, data):
                        raise IOError("Simulated disk write failure")
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        f.close()

                return FailingFile()

            with patch("os.fdopen", side_effect=failing_fdopen):
                with pytest.raises(IOError):
                    vault_storage.write_vault(b"corrupt data")

            # Original vault must still be intact
            assert vault_storage.read_vault() == original_content

            # No leftover .tmp files
            leftover_tmp = list(tmp_dir_path.glob("*.tmp"))
            assert len(leftover_tmp) == 0


# ---------------------------------------------------------------------------
# 14. Argon2id parameter upper-bound enforcement
# ---------------------------------------------------------------------------

def test_memory_cost_upper_bound():
    """A memory_cost exceeding the maximum must raise ValueError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    # memory_cost is at bytes 5-8 (uint32 big-endian)
    corrupted[5:9] = struct.pack(">I", MEMORY_COST_MAX + 1)
    with pytest.raises(ValueError, match="memory_cost"):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_time_cost_upper_bound():
    """A time_cost exceeding the maximum must raise ValueError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[9] = TIME_COST_MAX + 1   # time_cost is at byte 9
    with pytest.raises(ValueError, match="time_cost"):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_parallelism_upper_bound():
    """A parallelism value exceeding the maximum must raise ValueError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[10] = PARALLELISM_MAX + 1   # parallelism is at byte 10
    with pytest.raises(ValueError, match="parallelism"):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 15. Save and reload notes (data integrity)
# ---------------------------------------------------------------------------

def test_save_and_reload_notes():
    """
    Multiple notes saved to the vault must be fully recoverable, with all
    fields (id, title, content, created, modified) intact.
    """
    vault, _ = make_vault()
    master_key, notes = unlock_with_password(vault, VALID_PASSWORD)

    note1 = create_note("Python Notes", "Lists and loops")
    note2 = create_note("Shopping", "Bread, cheese, olives")
    notes.extend([note1, note2])

    vault = save_notes(vault, master_key, notes)
    _secure_zero(master_key)

    master_key, loaded_notes = unlock_with_password(vault, VALID_PASSWORD)
    assert len(loaded_notes) == 2
    assert loaded_notes[0]["title"] == "Python Notes"
    assert loaded_notes[1]["content"] == "Bread, cheese, olives"
    assert loaded_notes[0]["id"] == note1["id"]
    _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 16. create_note and update_note helpers
# ---------------------------------------------------------------------------

def test_create_note():
    """create_note must populate all required fields."""
    note = create_note("Test", "Content")
    assert "id" in note
    assert "created" in note
    assert "modified" in note
    assert note["title"] == "Test"
    assert note["content"] == "Content"


def test_update_note():
    """update_note must refresh the modified timestamp."""
    import time
    note = create_note("Old", "Old content")
    old_modified = note["modified"]
    time.sleep(0.01)   # Ensure the timestamp advances
    update_note(note, title="New", content="New content")
    assert note["title"] == "New"
    assert note["content"] == "New content"
    assert note["modified"] >= old_modified


# ---------------------------------------------------------------------------
# 17. Invalid recovery key format
# ---------------------------------------------------------------------------

def test_invalid_recovery_key_format():
    """An unparseable recovery key string must raise VaultError."""
    vault, _ = make_vault()
    with pytest.raises(VaultError):
        unlock_with_recovery_key(vault, "INVALID-KEY-!!!!")


# ---------------------------------------------------------------------------
# 18. Correct format but wrong recovery key
# ---------------------------------------------------------------------------

def test_wrong_recovery_key_correct_format():
    """A well-formed but incorrect recovery key must raise VaultError."""
    vault, _ = make_vault()
    # 32 zero-bytes → valid Base32, wrong key
    wrong_key = "AAAA" * 13  # Approximates a Base32 string of wrong key
    with pytest.raises(VaultError):
        unlock_with_recovery_key(vault, wrong_key)


# ---------------------------------------------------------------------------
# 19. _secure_zero zeroes a bytearray
# ---------------------------------------------------------------------------

def test_secure_zero():
    """_secure_zero must overwrite every byte with 0x00."""
    ba = bytearray(b"sensitive-data")
    _secure_zero(ba)
    assert all(b == 0 for b in ba)
