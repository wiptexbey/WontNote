"""
test_crypto_core.py — WontNote Encryption Core Test Suite
==========================================================
Covered scenarios:
     1. Open vault with the correct password
     2. Reject wrong password (VaultError)
     3. Open vault with recovery key
     4. Change password: old password no longer works, notes preserved
     5. Regenerate recovery key: old key no longer works
     6. Header tampering tests (recovery slot, password slot, notes nonce)
     7. Encrypted notes block tampering tests (middle byte, tag byte)
     8. Unknown format version rejected
     9. Invalid magic bytes rejected
    10. Short password rejected at creation
    11. Short password rejected when changing password
    12. Fresh nonce generated on every save
    13. Argon2id parameter bounds enforcement (lower & upper)
    14. Save and reload notes (data integrity)
    15. Invalid recovery key format and parsing (whitespace, case, garbage)
    16. Wrong recovery key with valid format
    17. _secure_zero zeroes a bytearray
    18. change_password consistency with custom Argon2id parameters
    19. Unicode normalization (NFKC) for passwords (e.g. 'ş' NFC vs NFD)
    20. Tampered master key raises VaultError
    21. Best-effort zeroization upon decryption failure (pattern verification)
    22. Header length constant and struct freeze guard
    23. regenerate_recovery_key cycle (old fails, new works, password works)
    24. change_password preserves recovery key and notes
    25. Invalid vault lengths (empty, short, exact header length)
    26. save_notes verification with wrong and all-zero keys
"""

import os
import struct
import sys
from pathlib import Path

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
    HEADER_LENGTH,
    MIN_PASSWORD_LENGTH,
    create_vault,
    unlock_with_password,
    unlock_with_recovery_key,
    save_notes,
    change_password,
    regenerate_recovery_key,
    create_note,
    _secure_zero,
    _format_recovery_key,
    _parse_recovery_key,
    _pack_vault_and_encrypt_notes,
    _argon2id_derive,
    _aesgcm_wrap,
    _hkdf_derive,
    _unpack_vault,
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
# 6. Header tampering tests (computed offsets from struct layout)
# ---------------------------------------------------------------------------

# Layout: magic(4) | version(1) | m(4) | t(1) | p(1) | pw_salt(16) | pw_nonce(12) | pw_ct(48)
#         | rec_salt(16) | rec_nonce(12) | rec_ct(48) | notes_nonce(12) | notes_ciphertext
OFFSET_PASSWORD_SALT       = struct.calcsize(">4sBIBB")              # 11
OFFSET_PASSWORD_NONCE      = struct.calcsize(">4sBIBB16s")           # 27
OFFSET_PASSWORD_CIPHERTEXT = struct.calcsize(">4sBIBB16s12s")        # 39
OFFSET_RECOVERY_SALT       = struct.calcsize(">4sBIBB16s12s48s")     # 87
OFFSET_RECOVERY_NONCE      = struct.calcsize(">4sBIBB16s12s48s16s")  # 103
OFFSET_RECOVERY_CIPHERTEXT = struct.calcsize(">4sBIBB16s12s48s16s12s") # 115
OFFSET_NOTES_NONCE         = struct.calcsize(">4sBIBB16s12s48s16s12s48s") # 163
OFFSET_ENCRYPTED_NOTES     = struct.calcsize(">4sBIBB16s12s48s16s12s48s12s") # 175


def test_tamper_recovery_slot_fails_password_unlock():
    """
    Case (a): Flipping one byte in the RECOVERY slot (salt, nonce, ciphertext)
    and unlocking WITH THE PASSWORD must fail with VaultError.
    Only the AES-GCM header AAD integrity check can catch this tamper,
    since password unlock does not read or decrypt the recovery slot.
    """
    vault, _ = make_vault()
    for offset in (OFFSET_RECOVERY_SALT, OFFSET_RECOVERY_NONCE, OFFSET_RECOVERY_CIPHERTEXT):
        corrupted = bytearray(vault)
        corrupted[offset] ^= 0xFF
        with pytest.raises(VaultError):
            unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_tamper_password_slot_ciphertext_fails_password_unlock():
    """Case (b): Flipping one byte in the password slot ciphertext must fail with VaultError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[OFFSET_PASSWORD_CIPHERTEXT] ^= 0xFF
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_tamper_notes_nonce_fails_unlock():
    """Case (c): Flipping one byte of the notes nonce must fail with VaultError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[OFFSET_NOTES_NONCE] ^= 0xFF
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


# ---------------------------------------------------------------------------
# 7. Encrypted notes block tampering tests
# ---------------------------------------------------------------------------

def test_tamper_encrypted_notes_middle_fails_unlock():
    """Case (d): Flipping one byte in the middle of the encrypted notes block must fail with VaultError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    notes_len = len(corrupted) - OFFSET_ENCRYPTED_NOTES
    mid_offset = OFFSET_ENCRYPTED_NOTES + notes_len // 2
    corrupted[mid_offset] ^= 0xFF
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_tamper_encrypted_notes_tag_fails_unlock():
    """Flipping the last byte (GCM authentication tag) of notes block must fail with VaultError."""
    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[-1] ^= 0xFF
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_tamper_recovery_slot_fails_recovery_unlock():
    """Case (e): Flipping a byte in the recovery slot and unlocking with recovery key must fail with VaultError."""
    vault, recovery_str = make_vault()
    corrupted = bytearray(vault)
    corrupted[OFFSET_RECOVERY_CIPHERTEXT] ^= 0xFF
    with pytest.raises(VaultError):
        unlock_with_recovery_key(bytes(corrupted), recovery_str)


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


# ---------------------------------------------------------------------------
# 20. change_password with custom Argon2id parameters
# ---------------------------------------------------------------------------

def test_change_password_custom_argon2_parameters():
    """
    When a vault has non-default Argon2id parameters, change_password must derive
    the new wrap key using those same parameters and write them to the new header.
    Unlocking with the new password must succeed, and the old password must fail.
    """
    custom_m = 64
    custom_t = 1
    custom_p = 1
    master_key = bytearray(os.urandom(32))
    raw_recovery = os.urandom(32)

    try:
        pw_salt = os.urandom(16)
        wrap_key_pw = _argon2id_derive(
            VALID_PASSWORD.encode("utf-8"),
            pw_salt,
            memory_cost=custom_m,
            time_cost=custom_t,
            parallelism=custom_p,
        )
        try:
            pw_nonce, pw_ct = _aesgcm_wrap(wrap_key_pw, bytes(master_key))
        finally:
            _secure_zero(wrap_key_pw)

        rec_salt = os.urandom(16)
        wrap_key_rec = _hkdf_derive(raw_recovery, rec_salt)
        try:
            rec_nonce, rec_ct = _aesgcm_wrap(wrap_key_rec, bytes(master_key))
        finally:
            _secure_zero(wrap_key_rec)

        vault = _pack_vault_and_encrypt_notes(
            custom_m, custom_t, custom_p,
            pw_salt, pw_nonce, pw_ct,
            rec_salt, rec_nonce, rec_ct,
            master_key,
            [{"id": "test", "title": "Custom Params", "content": "Works"}],
        )

        # Change password using master_key
        new_vault = change_password(vault, master_key, VALID_PASSWORD_2)

        # Header in new vault must preserve custom Argon2id parameters
        fields = _unpack_vault(new_vault)
        assert fields["memory_cost"] == custom_m
        assert fields["time_cost"] == custom_t
        assert fields["parallelism"] == custom_p

        # Old password must no longer work
        with pytest.raises(VaultError):
            unlock_with_password(new_vault, VALID_PASSWORD)

        # New password must work and recover notes
        mk, notes = unlock_with_password(new_vault, VALID_PASSWORD_2)
        assert len(notes) == 1
        assert notes[0]["title"] == "Custom Params"
        _secure_zero(mk)

    finally:
        _secure_zero(master_key)


# ---------------------------------------------------------------------------
# 21. Recovery key format and parsing
# ---------------------------------------------------------------------------

def test_recovery_key_format_and_parsing():
    """
    Recovery key display formatting must strip '=' padding.
    Parsing must tolerate lowercase, extra spaces, and hyphens.
    Garbage or wrong length input must raise VaultError (never raw binascii/ValueError).
    """
    raw = os.urandom(32)
    formatted = _format_recovery_key(raw)

    # Must not contain '=' padding
    assert "=" not in formatted
    # Must be 13 groups of 4 characters joined by hyphens (total 64 chars)
    groups = formatted.split("-")
    assert len(groups) == 13
    assert all(len(g) == 4 for g in groups)

    # Round-trip decode
    assert _parse_recovery_key(formatted) == raw

    # Lowercase tolerance
    assert _parse_recovery_key(formatted.lower()) == raw

    # Extra spaces and mixed hyphens tolerance
    messy = f"  {formatted[:10]}   -   {formatted[10:]}  "
    assert _parse_recovery_key(messy) == raw

    # Garbage / invalid characters must raise VaultError
    with pytest.raises(VaultError):
        _parse_recovery_key("NOT-VALID-BASE32-!@#$")

    # Wrong length (e.g. valid Base32 characters but wrong decoded length)
    with pytest.raises(VaultError):
        _parse_recovery_key("AAAA-BBBB-CCCC")


# ---------------------------------------------------------------------------
# 22. Password normalization (Unicode NFKC)
# ---------------------------------------------------------------------------

def test_password_normalization_nfc_nfd():
    """
    Unicode normalization (NFKC) ensures NFC and NFD representations of characters
    (such as 'ş' vs 's\\u0327') produce identical keys and open the same vault.
    Minimum password length of 12 is checked after normalization.
    """
    import unicodedata

    base_nfc = "Password123ş"
    base_nfd = unicodedata.normalize("NFD", base_nfc)

    assert base_nfc != base_nfd

    vault, _ = create_vault(base_nfc)

    # Unlock using NFD form must succeed
    mk, notes = unlock_with_password(vault, base_nfd)
    assert len(notes) == 0
    _secure_zero(mk)

    # Unlock using NFC form must also succeed
    mk, notes = unlock_with_password(vault, base_nfc)
    assert len(notes) == 0
    _secure_zero(mk)

    # Length check enforced after normalization
    short_pw = "1234567890" + "ş"  # 11 characters
    with pytest.raises(ValueError, match="at least"):
        create_vault(short_pw)


# ---------------------------------------------------------------------------
# 23. Argon2id parameter bounds and error handling
# ---------------------------------------------------------------------------

def test_argon2_lower_bounds_rejected():
    """
    Argon2id lower bounds must be enforced when reading a header:
    parallelism >= 1, time_cost >= 1, memory_cost >= 8 * parallelism.
    """
    vault, _ = make_vault()

    # parallelism < 1
    corrupted = bytearray(vault)
    corrupted[10] = 0  # parallelism = 0
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)

    # time_cost < 1
    corrupted = bytearray(vault)
    corrupted[9] = 0  # time_cost = 0
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)

    # memory_cost < 8 * parallelism
    corrupted = bytearray(vault)
    corrupted[10] = 2
    corrupted[5:9] = struct.pack(">I", 15)  # 15 < 8 * 2
    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)


def test_tampered_master_key_raises_vault_error():
    """
    In change_password and regenerate_recovery_key, a wrong/invalid master key
    must raise VaultError, not a raw cryptography.exceptions.InvalidTag.
    """
    vault, _ = make_vault()
    wrong_master_key = bytearray(b"W" * 32)

    with pytest.raises(VaultError):
        change_password(vault, wrong_master_key, VALID_PASSWORD_2)

    with pytest.raises(VaultError):
        regenerate_recovery_key(vault, wrong_master_key)


# ---------------------------------------------------------------------------
# 24. Best-effort zeroization upon decryption failure
# ---------------------------------------------------------------------------

def test_best_effort_zeroization_on_failure(monkeypatch):
    """
    If decrypting the notes block fails after unwrapping the master key,
    the intermediate master key bytearray must be zeroized before VaultError propagates.
    We monkeypatch crypto_core._aesgcm_unwrap to return a known pattern (b"\\x42" * 32),
    spy on _secure_zero recording a COPY of each buffer before zeroing,
    make the notes decrypt fail, and assert that a buffer equal to the pattern was zeroed.
    """
    import wontnote.crypto_core as cc

    vault, _ = make_vault()
    corrupted = bytearray(vault)
    corrupted[-1] ^= 0xFF  # Corrupt the notes block GCM tag

    pattern = b"\x42" * 32
    monkeypatch.setattr(cc, "_aesgcm_unwrap", lambda *args, **kwargs: pattern)

    zeroed_buffers = []
    original_secure_zero = cc._secure_zero

    def spy_secure_zero(ba: bytearray):
        zeroed_buffers.append(bytes(ba))
        original_secure_zero(ba)

    monkeypatch.setattr(cc, "_secure_zero", spy_secure_zero)

    with pytest.raises(VaultError):
        unlock_with_password(bytes(corrupted), VALID_PASSWORD)

    # Assert that a buffer equal to the known pattern was zeroed
    assert pattern in zeroed_buffers


# ---------------------------------------------------------------------------
# 25. Header length and deduplicated encryption logic
# ---------------------------------------------------------------------------

def test_header_length_constant_and_struct():
    """
    Verify that len(header) == HEADER_LENGTH == 175 and that encrypting the same
    notes twice produces different nonces and different ciphertexts.
    """
    vault, _ = make_vault()
    fields = _unpack_vault(vault)
    assert len(fields["aad"]) == HEADER_LENGTH == 175

    # Encrypting twice produces different nonces and ciphertexts
    mk, notes = unlock_with_password(vault, VALID_PASSWORD)
    v1 = save_notes(vault, mk, notes)
    v2 = save_notes(vault, mk, notes)
    assert v1 != v2
    f1 = _unpack_vault(v1)
    f2 = _unpack_vault(v2)
    assert f1["notes_nonce"] != f2["notes_nonce"]
    assert f1["encrypted_notes"] != f2["encrypted_notes"]
    _secure_zero(mk)


def test_regenerate_recovery_key_cycle():
    """
    After regenerate_recovery_key:
    - The old recovery key no longer opens the vault.
    - The new recovery key opens the vault.
    - The existing password still opens the vault.
    """
    vault, old_rec = make_vault()
    mk, _ = unlock_with_password(vault, VALID_PASSWORD)
    new_vault, new_rec = regenerate_recovery_key(vault, mk)
    _secure_zero(mk)

    # Old key fails
    with pytest.raises(VaultError):
        unlock_with_recovery_key(new_vault, old_rec)

    # New key succeeds
    mk, notes = unlock_with_recovery_key(new_vault, new_rec)
    assert isinstance(notes, list)
    _secure_zero(mk)

    # Password still succeeds
    mk, notes = unlock_with_password(new_vault, VALID_PASSWORD)
    assert isinstance(notes, list)
    _secure_zero(mk)


# ---------------------------------------------------------------------------
# 26. Additional recovery key, length, and save_notes verification tests
# ---------------------------------------------------------------------------

def test_change_password_preserves_recovery_key_and_notes():
    """
    After change_password:
    - The recovery key must still open the vault.
    - Notes must remain intact when unlocked with the recovery key.
    """
    vault, rec_key = make_vault()
    mk, notes = unlock_with_password(vault, VALID_PASSWORD)
    notes.append(create_note("Secret", "Preserved Content"))
    vault = save_notes(vault, mk, notes)
    vault = change_password(vault, mk, VALID_PASSWORD_2)
    _secure_zero(mk)

    mk2, loaded_notes = unlock_with_recovery_key(vault, rec_key)
    assert len(loaded_notes) == 1
    assert loaded_notes[0]["title"] == "Secret"
    assert loaded_notes[0]["content"] == "Preserved Content"
    _secure_zero(mk2)


def test_invalid_vault_length_raises_vault_error():
    """Vault bytes that are empty, shorter than HEADER_LENGTH, or exactly HEADER_LENGTH must raise VaultError."""
    with pytest.raises(VaultError):
        unlock_with_password(b"", VALID_PASSWORD)

    with pytest.raises(VaultError):
        unlock_with_password(b"SHORT", VALID_PASSWORD)

    with pytest.raises(VaultError):
        unlock_with_password(b"X" * (HEADER_LENGTH - 1), VALID_PASSWORD)

    with pytest.raises(VaultError):
        unlock_with_password(b"X" * HEADER_LENGTH, VALID_PASSWORD)


def test_save_notes_with_wrong_or_zero_key_raises_vault_error():
    """
    save_notes with a wrong master key or an all-zero key must raise VaultError,
    and the original vault bytes must remain unchanged.
    """
    vault, _ = make_vault()
    original_vault = bytes(vault)

    wrong_key = bytearray(os.urandom(32))
    with pytest.raises(VaultError):
        save_notes(vault, wrong_key, [{"title": "Won't save"}])

    zero_key = bytearray(32)
    with pytest.raises(VaultError):
        save_notes(vault, zero_key, [{"title": "Won't save"}])

    assert vault == original_vault
    mk, notes = unlock_with_password(vault, VALID_PASSWORD)
    assert len(notes) == 0
    _secure_zero(mk)

