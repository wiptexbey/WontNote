"""
crypto_core.py — WontNote Encryption Core
==========================================
This module is fully independent of the GUI layer.
It contains only pure cryptographic operations.

Passwords, keys, and plaintext note data are never logged, printed,
written to temporary files, or included in error messages.

Key Architecture (summary):
    - MASTER KEY: 32 random bytes; encrypts notes for the vault's lifetime.
    - PASSWORD SLOT:  user password → Argon2id → 32-byte wrap key → AES-256-GCM(master_key).
    - RECOVERY SLOT:  32-byte random recovery key → HKDF-SHA256 → 32-byte wrap key → AES-256-GCM(master_key).
    - NOTES BLOCK:    JSON UTF-8 → AES-256-GCM (master key, fresh nonce).

Binary File Format (version 1):
    [4 B]  magic bytes       b"WNT1"
    [1 B]  format version    0x01
    [4 B]  memory_cost       (uint32 big-endian)
    [1 B]  time_cost         (uint8)
    [1 B]  parallelism       (uint8)
    [16 B] password slot salt
    [12 B] password slot nonce
    [48 B] password slot encrypted master key  (32 B ciphertext + 16 B GCM tag)
    [16 B] recovery slot HKDF salt
    [12 B] recovery slot nonce
    [48 B] recovery slot encrypted master key
    [12 B] notes block nonce
    --- Everything above (175 B) is passed as AAD to AES-GCM ---
    [N  B] encrypted notes block (N bytes + 16-byte GCM tag)

Because the entire header is used as AAD, any tampering with header fields
causes authentication to fail (integrity protection).
"""

import json
import os
import struct
import unicodedata
from base64 import b32encode, b32decode

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from wontnote.notes import create_note, update_note

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC_BYTES     = b"WNT1"       # File identifier — must not change between versions
FORMAT_VERSION  = 0x01          # Binary format version (1 byte)

# Argon2id default parameters
DEFAULT_MEMORY_COST = 65_536    # 64 MiB
DEFAULT_TIME_COST   = 3
DEFAULT_PARALLELISM = 4
HASH_LENGTH         = 32        # bytes

# Argon2id parameter bounds
MEMORY_COST_MIN = 8             # KiB (enforced as >= 8 * parallelism)
TIME_COST_MIN   = 1
PARALLELISM_MIN = 1

MEMORY_COST_MAX = 1_048_576     # 1 GiB
TIME_COST_MAX   = 10
PARALLELISM_MAX = 16

# AES-GCM fixed sizes
NONCE_LENGTH        = 12        # bytes (96 bits)
GCM_TAG_LENGTH      = 16        # bytes (128 bits)
WRAPPED_CIPHER_LENGTH = HASH_LENGTH + GCM_TAG_LENGTH  # 48 bytes

# Salt sizes
PASSWORD_SALT_LENGTH  = 16      # bytes
RECOVERY_SALT_LENGTH  = 16      # bytes (HKDF salt)

# Recovery key
RECOVERY_KEY_LENGTH = 32        # bytes (raw)
HKDF_INFO = b"wontnote-recovery-v1"   # HKDF context label

# Note data
MIN_PASSWORD_LENGTH = 12

# Struct format for the 175-byte vault header
HEADER_STRUCT_FORMAT = ">4sBIBB16s12s48s16s12s48s12s"
HEADER_LENGTH = struct.calcsize(HEADER_STRUCT_FORMAT)
if HEADER_LENGTH != 175:
    raise RuntimeError(f"Expected header length 175, got {HEADER_LENGTH}")


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

class VaultError(ValueError):
    """
    Raised when the vault cannot be opened due to a wrong password,
    wrong recovery key, corrupted data, or invalid parameters.

    The error message is intentionally generic — it does not reveal
    which specific field was incorrect.
    Subclasses ValueError for backward-compatibility with callers and tests.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _secure_zero(ba: bytearray) -> None:
    """
    Overwrite every byte of the bytearray with zero.

    NOTE: This is best-effort in Python. Depending on the CPython version,
    garbage collector timing, and memory optimisations, there is no hard
    guarantee that sensitive data will be fully erased from RAM.
    """
    for i in range(len(ba)):
        ba[i] = 0


def _normalize_password(password: str) -> str:
    """Normalize password to Unicode NFKC form."""
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    return unicodedata.normalize("NFKC", password)


def _argon2id_derive(
    password_bytes: bytes,
    salt: bytes,
    memory_cost: int = DEFAULT_MEMORY_COST,
    time_cost: int   = DEFAULT_TIME_COST,
    parallelism: int = DEFAULT_PARALLELISM,
) -> bytearray:
    """
    Derive a 32-byte key from a password using Argon2id.
    Returns a bytearray; the caller must zero it after use.
    Wraps any argon2-cffi exception into VaultError.
    """
    try:
        raw = hash_secret_raw(
            secret=password_bytes,
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=HASH_LENGTH,
            type=Type.ID,
        )
        return bytearray(raw)
    except Exception as e:
        raise VaultError("Could not open vault.") from e


def _hkdf_derive(recovery_key_bytes: bytes, salt: bytes) -> bytearray:
    """
    Derive a 32-byte wrapping key from a high-entropy recovery key using
    HKDF-SHA256. Argon2id is unnecessary because the input already
    contains 32 bytes of random entropy.
    """
    hkdf = HKDF(
        algorithm=SHA256(),
        length=HASH_LENGTH,
        salt=salt,
        info=HKDF_INFO,
    )
    return bytearray(hkdf.derive(recovery_key_bytes))


def _aesgcm_wrap(wrap_key: bytearray, plaintext: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt *plaintext* with AES-256-GCM using *wrap_key*.
    A fresh random nonce is generated on every call — the same nonce
    is never reused with the same key.

    Returns: (nonce, ciphertext_with_tag)
    """
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(bytes(wrap_key))   # temporary bytes copy required by the library
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def _aesgcm_unwrap(
    wrap_key: bytearray,
    nonce: bytes,
    ciphertext: bytes,
    aad: bytes | None = None,
) -> bytes:
    """
    Decrypt *ciphertext* with AES-256-GCM.
    The cryptography library verifies the GCM tag automatically;
    it raises InvalidTag on failure.
    """
    aesgcm = AESGCM(bytes(wrap_key))
    return aesgcm.decrypt(nonce, ciphertext, aad)


# ---------------------------------------------------------------------------
# File format: packing and unpacking
# ---------------------------------------------------------------------------

def _validate_params(memory_cost: int, time_cost: int, parallelism: int) -> None:
    """
    Verify that Argon2id parameters read from the file header fall within
    the defined valid lower and upper bounds.
    """
    if parallelism < PARALLELISM_MIN or parallelism > PARALLELISM_MAX:
        raise VaultError(
            f"parallelism ({parallelism}) out of bounds [{PARALLELISM_MIN}, {PARALLELISM_MAX}]."
        )
    if time_cost < TIME_COST_MIN or time_cost > TIME_COST_MAX:
        raise VaultError(
            f"time_cost ({time_cost}) out of bounds [{TIME_COST_MIN}, {TIME_COST_MAX}]."
        )
    min_memory = 8 * parallelism
    if memory_cost < min_memory or memory_cost > MEMORY_COST_MAX:
        raise VaultError(
            f"memory_cost ({memory_cost}) out of bounds [{min_memory}, {MEMORY_COST_MAX}]."
        )


def _pack_vault_and_encrypt_notes(
    memory_cost: int,
    time_cost: int,
    parallelism: int,
    password_salt: bytes,
    password_nonce: bytes,
    password_ciphertext: bytes,
    recovery_salt: bytes,
    recovery_nonce: bytes,
    recovery_ciphertext: bytes,
    master_key: bytearray,
    notes_data: bytes | list,
) -> bytes:
    """
    Build the vault header (used as AAD), encrypt notes using AES-256-GCM
    with a fresh random 12-byte nonce, and return the complete packed vault.

    A fresh random 12-byte nonce is generated on EVERY call.
    The entire header is passed as AAD to authenticate the notes block.
    """
    if isinstance(notes_data, list):
        notes_json = _notes_to_json(notes_data)
    else:
        notes_json = notes_data

    notes_nonce = os.urandom(NONCE_LENGTH)
    header = struct.pack(
        HEADER_STRUCT_FORMAT,
        MAGIC_BYTES,
        FORMAT_VERSION,
        memory_cost,
        time_cost,
        parallelism,
        password_salt,
        password_nonce,
        password_ciphertext,
        recovery_salt,
        recovery_nonce,
        recovery_ciphertext,
        notes_nonce,
    )
    assert len(header) == HEADER_LENGTH, "Header length mismatch."

    try:
        aesgcm = AESGCM(bytes(master_key))
        encrypted_notes = aesgcm.encrypt(notes_nonce, notes_json, header)
    except Exception as e:
        raise VaultError("Could not open vault.") from e

    return header + encrypted_notes


def _unpack_vault(vault_bytes: bytes) -> dict:
    """
    Parse vault bytes, validate magic bytes, version, and parameters,
    and return all fields as a dictionary.

    Raises:
        VaultError: Unknown format, truncated data, or parameter bounds exceeded.
    """
    if len(vault_bytes) < HEADER_LENGTH + GCM_TAG_LENGTH:
        raise VaultError("Vault file is too short or corrupted.")

    header_bytes = vault_bytes[:HEADER_LENGTH]
    (
        magic,
        version,
        memory_cost,
        time_cost,
        parallelism,
        password_salt,
        password_nonce,
        password_ciphertext,
        recovery_salt,
        recovery_nonce,
        recovery_ciphertext,
        notes_nonce,
    ) = struct.unpack(HEADER_STRUCT_FORMAT, header_bytes)

    if magic != MAGIC_BYTES:
        raise VaultError("Invalid file format: magic bytes do not match.")

    if version != FORMAT_VERSION:
        raise VaultError(f"Unsupported format version: {version}.")

    # Enforce parameter bounds
    _validate_params(memory_cost, time_cost, parallelism)

    encrypted_notes = vault_bytes[HEADER_LENGTH:]
    if len(encrypted_notes) < GCM_TAG_LENGTH:
        raise VaultError("Encrypted notes block is too short.")

    return {
        "memory_cost":          memory_cost,
        "time_cost":            time_cost,
        "parallelism":          parallelism,
        "password_salt":        password_salt,
        "password_nonce":       password_nonce,
        "password_ciphertext":  password_ciphertext,
        "recovery_salt":        recovery_salt,
        "recovery_nonce":       recovery_nonce,
        "recovery_ciphertext":  recovery_ciphertext,
        "notes_nonce":          notes_nonce,
        "aad":                  header_bytes,
        "encrypted_notes":      encrypted_notes,
    }


# ---------------------------------------------------------------------------
# Note data helpers
# ---------------------------------------------------------------------------

def _notes_to_json(notes: list) -> bytes:
    """Serialise a note list to UTF-8 JSON bytes."""
    return json.dumps(notes, ensure_ascii=False).encode("utf-8")


def _json_to_notes(data: bytes) -> list:
    """Deserialise UTF-8 JSON bytes to a note list."""
    return json.loads(data.decode("utf-8"))


# ---------------------------------------------------------------------------
# Recovery key helpers
# ---------------------------------------------------------------------------

def _format_recovery_key(raw_bytes: bytes) -> str:
    """
    Base32-encode raw bytes, strip trailing '=' padding, and split into
    groups of 4 characters separated by hyphens for human-readable display.

    Example: ABCD-EFGH-IJKL-...
    """
    b32 = b32encode(raw_bytes).decode("ascii").rstrip("=")
    groups = [b32[i:i + 4] for i in range(0, len(b32), 4)]
    return "-".join(groups)


def _parse_recovery_key(recovery_str: str) -> bytes:
    """
    Parse a user-supplied recovery key string: strip hyphens and spaces,
    convert to uppercase, restore '=' Base32 padding, then decode.

    Decoding tolerates lowercase characters, spaces, and hyphens.
    Malformed input (bad characters, invalid length, wrong decoded length)
    must raise VaultError.

    Raises:
        VaultError: If the key cannot be decoded or is invalid.
    """
    if not isinstance(recovery_str, str):
        raise VaultError("Could not open vault.")

    cleaned = recovery_str.replace("-", "").replace(" ", "").upper()
    if not cleaned:
        raise VaultError("Could not open vault.")

    # Base32 requires length to be a multiple of 8 when padded
    remainder = len(cleaned) % 8
    if remainder != 0:
        cleaned += "=" * (8 - remainder)

    try:
        raw = b32decode(cleaned)
    except Exception as e:
        raise VaultError("Could not open vault.") from e

    if len(raw) != RECOVERY_KEY_LENGTH:
        raise VaultError("Could not open vault.")

    return raw


# ---------------------------------------------------------------------------
# Internal: decrypt master key and notes
# ---------------------------------------------------------------------------

def _unwrap_master_key_and_notes(
    fields: dict, wrap_key: bytearray, slot: str
) -> tuple[bytearray, list]:
    """
    Unwrap the master key from the given slot using *wrap_key*, then
    decrypt the notes block. On failure a generic VaultError is raised —
    the caller cannot tell which field was wrong.

    If unwrapping or decrypting fails, intermediate master_key is zeroized
    before the exception propagates.

    slot: "password" or "recovery"
    """
    try:
        if slot == "password":
            nonce      = fields["password_nonce"]
            ciphertext = fields["password_ciphertext"]
        else:
            nonce      = fields["recovery_nonce"]
            ciphertext = fields["recovery_ciphertext"]

        # Unwrap the master key
        try:
            master_key_bytes = _aesgcm_unwrap(wrap_key, nonce, ciphertext)
        except Exception as e:
            raise VaultError("Could not open vault.") from e

        master_key = bytearray(master_key_bytes)
        success = False
        try:
            try:
                aesgcm = AESGCM(bytes(master_key))
                notes_json = aesgcm.decrypt(
                    fields["notes_nonce"],
                    fields["encrypted_notes"],
                    fields["aad"],
                )
            except Exception as e:
                raise VaultError("Could not open vault.") from e

            try:
                notes = _json_to_notes(notes_json)
            except Exception as e:
                raise VaultError("Could not open vault.") from e

            success = True
            return master_key, notes
        finally:
            if not success:
                _secure_zero(master_key)

    finally:
        _secure_zero(wrap_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_vault(password: str) -> tuple[bytes, str]:
    """
    Create a new encrypted vault.

    Parameters:
        password: User password (minimum 12 characters).

    Returns:
        (vault_bytes, recovery_key_str)
        recovery_key_str is returned exactly once; show it to the user
        and then clear it from memory.

    Raises:
        ValueError: If the password is too short.
    """
    normalized = _normalize_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    # 1. Master key: 32 random bytes
    master_key = bytearray(os.urandom(HASH_LENGTH))

    try:
        # 2a. Password slot: Argon2id → wrap key → AES-GCM
        password_salt = os.urandom(PASSWORD_SALT_LENGTH)
        password_bytes = normalized.encode("utf-8")
        wrap_key = _argon2id_derive(password_bytes, password_salt)
        try:
            password_nonce, password_ciphertext = _aesgcm_wrap(
                wrap_key, bytes(master_key)
            )
        finally:
            _secure_zero(wrap_key)

        # 2b. Recovery slot: random recovery key → HKDF → AES-GCM
        raw_recovery = os.urandom(RECOVERY_KEY_LENGTH)
        recovery_salt = os.urandom(RECOVERY_SALT_LENGTH)
        wrap_key = _hkdf_derive(raw_recovery, recovery_salt)
        try:
            recovery_nonce, recovery_ciphertext = _aesgcm_wrap(
                wrap_key, bytes(master_key)
            )
        finally:
            _secure_zero(wrap_key)

        # 3 & 4. Build header + encrypt notes with master key
        vault_bytes = _pack_vault_and_encrypt_notes(
            DEFAULT_MEMORY_COST,
            DEFAULT_TIME_COST,
            DEFAULT_PARALLELISM,
            password_salt,
            password_nonce,
            password_ciphertext,
            recovery_salt,
            recovery_nonce,
            recovery_ciphertext,
            master_key,
            [],
        )

        return vault_bytes, _format_recovery_key(raw_recovery)

    finally:
        _secure_zero(master_key)


def unlock_with_password(vault_bytes: bytes, password: str) -> tuple[bytearray, list]:
    """
    Open the vault using the user's password.

    Returns:
        (master_key, notes)
        master_key is a bytearray; the caller must zero it after use.

    Raises:
        VaultError: Wrong password, corrupted data, or invalid format/parameters.
    """
    fields = _unpack_vault(vault_bytes)
    normalized = _normalize_password(password)
    password_bytes = normalized.encode("utf-8")
    wrap_key = _argon2id_derive(
        password_bytes,
        fields["password_salt"],
        fields["memory_cost"],
        fields["time_cost"],
        fields["parallelism"],
    )
    return _unwrap_master_key_and_notes(fields, wrap_key, "password")


def unlock_with_recovery_key(
    vault_bytes: bytes, recovery_key_str: str
) -> tuple[bytearray, list]:
    """
    Open the vault using the recovery key.

    Returns:
        (master_key, notes)

    Raises:
        VaultError: Invalid recovery key or corrupted data.
    """
    fields = _unpack_vault(vault_bytes)
    raw_recovery = _parse_recovery_key(recovery_key_str)
    wrap_key = _hkdf_derive(raw_recovery, fields["recovery_salt"])
    return _unwrap_master_key_and_notes(fields, wrap_key, "recovery")


def _decrypt_notes_block(fields: dict, master_key: bytearray) -> bytes:
    """
    Authenticate and decrypt the existing notes block using master_key and header AAD.
    Raises VaultError("Could not open vault.") if authentication or decryption fails.
    """
    try:
        aesgcm = AESGCM(bytes(master_key))
        return aesgcm.decrypt(
            fields["notes_nonce"],
            fields["encrypted_notes"],
            fields["aad"],
        )
    except Exception as e:
        raise VaultError("Could not open vault.") from e


def save_notes(vault_bytes: bytes, master_key: bytearray, notes: list) -> bytes:
    """
    Re-encrypt the notes list with a fresh nonce and return updated vault bytes.

    Before encrypting, verifies the given master_key by decrypting the existing
    notes block with it and the existing header as AAD. On failure, raises
    VaultError("Could not open vault.").

    The master key and both key slots are unchanged; only the notes block
    is re-encrypted. A new nonce is mandatory on every save.

    Returns:
        Updated vault bytes (new notes nonce).
    """
    fields = _unpack_vault(vault_bytes)
    _decrypt_notes_block(fields, master_key)
    return _pack_vault_and_encrypt_notes(
        fields["memory_cost"],
        fields["time_cost"],
        fields["parallelism"],
        fields["password_salt"],
        fields["password_nonce"],
        fields["password_ciphertext"],
        fields["recovery_salt"],
        fields["recovery_nonce"],
        fields["recovery_ciphertext"],
        master_key,
        notes,
    )


def change_password(
    vault_bytes: bytes, master_key: bytearray, new_password: str
) -> bytes:
    """
    Replace the password slot with a new salt and new encryption.
    The notes block is re-encrypted under the new AAD (because the header
    includes the password slot). The recovery slot is untouched.

    IMPORTANT: Because the header (= AAD) contains the password slot, changing
    the slot changes the AAD, so the notes block must be re-encrypted.
    That is why master_key is required as a parameter.

    Raises:
        ValueError: New password is too short.
        VaultError: Invalid master key or authentication failure.
    """
    normalized = _normalize_password(new_password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"New password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    fields = _unpack_vault(vault_bytes)
    notes_json = _decrypt_notes_block(fields, master_key)

    # Derive new wrap key from new password using the header's Argon2id parameters
    new_password_salt = os.urandom(PASSWORD_SALT_LENGTH)
    new_password_bytes = normalized.encode("utf-8")
    new_wrap_key = _argon2id_derive(
        new_password_bytes,
        new_password_salt,
        memory_cost=fields["memory_cost"],
        time_cost=fields["time_cost"],
        parallelism=fields["parallelism"],
    )
    try:
        new_password_nonce, new_password_ciphertext = _aesgcm_wrap(
            new_wrap_key, bytes(master_key)
        )
    finally:
        _secure_zero(new_wrap_key)

    # Re-encrypt notes under new header AAD using deduplicated helper
    return _pack_vault_and_encrypt_notes(
        fields["memory_cost"],
        fields["time_cost"],
        fields["parallelism"],
        new_password_salt,
        new_password_nonce,
        new_password_ciphertext,
        fields["recovery_salt"],
        fields["recovery_nonce"],
        fields["recovery_ciphertext"],
        master_key,
        notes_json,
    )


def regenerate_recovery_key(
    vault_bytes: bytes, master_key: bytearray
) -> tuple[bytes, str]:
    """
    Replace the recovery slot with a newly generated recovery key.
    The notes block is re-encrypted under the new AAD (because the header
    includes the recovery slot). The password slot is untouched.

    IMPORTANT: Because the header (= AAD) contains the recovery slot, changing
    the slot changes the AAD, so the notes block must be re-encrypted.

    Returns:
        (new_vault_bytes, new_recovery_key_str)

    Raises:
        VaultError: Invalid master key or authentication failure.
    """
    fields = _unpack_vault(vault_bytes)
    notes_json = _decrypt_notes_block(fields, master_key)

    new_raw_recovery = os.urandom(RECOVERY_KEY_LENGTH)
    new_recovery_salt = os.urandom(RECOVERY_SALT_LENGTH)
    new_wrap_key = _hkdf_derive(new_raw_recovery, new_recovery_salt)
    try:
        new_recovery_nonce, new_recovery_ciphertext = _aesgcm_wrap(
            new_wrap_key, bytes(master_key)
        )
    finally:
        _secure_zero(new_wrap_key)

    new_vault = _pack_vault_and_encrypt_notes(
        fields["memory_cost"],
        fields["time_cost"],
        fields["parallelism"],
        fields["password_salt"],
        fields["password_nonce"],
        fields["password_ciphertext"],
        new_recovery_salt,
        new_recovery_nonce,
        new_recovery_ciphertext,
        master_key,
        notes_json,
    )
    return new_vault, _format_recovery_key(new_raw_recovery)
