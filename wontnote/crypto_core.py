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
import uuid
from base64 import b32encode, b32decode
from datetime import datetime, timezone

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

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

# Upper bounds — prevent a malicious vault from locking the application
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

# Total header size in bytes (must stay in sync with _pack_vault/_unpack_vault)
_HEADER_SIZE = 175


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _secure_zero(ba: bytearray) -> None:
    """
    Overwrite every byte of the bytearray with zero.

    NOTE: This is best-effort in Python. Depending on the CPython version,
    garbage collector timing, and memory optimisations, there is no hard
    guarantee that sensitive data will be fully erased from RAM.
    """
    for i in range(len(ba)):
        ba[i] = 0


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
    """
    raw = hash_secret_raw(
        secret=password_bytes,
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=HASH_LENGTH,
        type=Type.ID,
    )
    # hash_secret_raw returns bytes; copy into a mutable bytearray
    return bytearray(raw)


def _hkdf_derive(recovery_key_bytes: bytes, salt: bytes) -> bytearray:
    """
    Derive a 32-byte wrapping key from a high-entropy recovery key using
    HKDF-SHA256.  Argon2id is unnecessary because the input already
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
    Verify that Argon2id parameters read from the file header do not exceed
    the defined upper bounds.  Prevents a malicious vault from exhausting
    system resources.
    """
    if memory_cost > MEMORY_COST_MAX:
        raise ValueError(
            f"memory_cost ({memory_cost}) exceeds the allowed maximum ({MEMORY_COST_MAX})."
        )
    if time_cost > TIME_COST_MAX:
        raise ValueError(
            f"time_cost ({time_cost}) exceeds the allowed maximum ({TIME_COST_MAX})."
        )
    if parallelism > PARALLELISM_MAX:
        raise ValueError(
            f"parallelism ({parallelism}) exceeds the allowed maximum ({PARALLELISM_MAX})."
        )


def _pack_vault(
    memory_cost: int,
    time_cost: int,
    parallelism: int,
    password_salt: bytes,
    password_nonce: bytes,
    password_ciphertext: bytes,
    recovery_salt: bytes,
    recovery_nonce: bytes,
    recovery_ciphertext: bytes,
    notes_nonce: bytes,
    encrypted_notes: bytes,
) -> bytes:
    """
    Pack all fields into a single binary blob (vault bytes).

    Header layout (= AAD region, 175 bytes):
        magic | version | memory_cost | time_cost | parallelism
        | password_salt | password_nonce | password_ciphertext
        | recovery_salt | recovery_nonce | recovery_ciphertext
        | notes_nonce

    Followed immediately by: encrypted_notes.
    """
    header = (
        MAGIC_BYTES                                     # 4 B
        + bytes([FORMAT_VERSION])                       # 1 B
        + struct.pack(">I", memory_cost)                # 4 B big-endian uint32
        + bytes([time_cost])                            # 1 B
        + bytes([parallelism])                          # 1 B
        + password_salt                                 # 16 B
        + password_nonce                                # 12 B
        + password_ciphertext                           # 48 B
        + recovery_salt                                 # 16 B
        + recovery_nonce                                # 12 B
        + recovery_ciphertext                           # 48 B
        + notes_nonce                                   # 12 B
    )
    # Total header: 4+1+4+1+1+16+12+48+16+12+48+12 = 175 bytes
    assert len(header) == _HEADER_SIZE, "Header size mismatch — internal error."
    return header + encrypted_notes


def _unpack_vault(vault_bytes: bytes) -> dict:
    """
    Parse vault bytes, validate magic bytes and version, and return all
    fields as a dictionary.

    Raises:
        ValueError: Unknown format, truncated data, or parameter bounds exceeded.
    """
    if len(vault_bytes) < _HEADER_SIZE + GCM_TAG_LENGTH:
        raise ValueError("Vault file is too short or corrupted.")

    pos = 0

    # Magic bytes (4 B)
    magic = vault_bytes[pos:pos + 4]; pos += 4
    if magic != MAGIC_BYTES:
        raise ValueError("Invalid file format: magic bytes do not match.")

    # Format version (1 B)
    version = vault_bytes[pos]; pos += 1
    if version != FORMAT_VERSION:
        raise ValueError(f"Unsupported format version: {version}.")

    # Argon2id parameters
    (memory_cost,) = struct.unpack(">I", vault_bytes[pos:pos + 4]); pos += 4
    time_cost   = vault_bytes[pos]; pos += 1
    parallelism = vault_bytes[pos]; pos += 1

    # Enforce parameter upper bounds before doing any expensive computation
    _validate_params(memory_cost, time_cost, parallelism)

    # Password slot
    password_salt        = vault_bytes[pos:pos + 16]; pos += 16
    password_nonce       = vault_bytes[pos:pos + 12]; pos += 12
    password_ciphertext  = vault_bytes[pos:pos + 48]; pos += 48

    # Recovery slot
    recovery_salt        = vault_bytes[pos:pos + 16]; pos += 16
    recovery_nonce       = vault_bytes[pos:pos + 12]; pos += 12
    recovery_ciphertext  = vault_bytes[pos:pos + 48]; pos += 48

    # Notes nonce
    notes_nonce = vault_bytes[pos:pos + 12]; pos += 12

    # The entire header is the AAD region
    aad = vault_bytes[:pos]

    # Encrypted notes block (remainder; includes GCM tag)
    encrypted_notes = vault_bytes[pos:]
    if len(encrypted_notes) < GCM_TAG_LENGTH:
        raise ValueError("Encrypted notes block is too short.")

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
        "aad":                  aad,
        "encrypted_notes":      encrypted_notes,
    }


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

class VaultError(Exception):
    """
    Raised when the vault cannot be opened due to a wrong password,
    wrong recovery key, or corrupted data.

    The error message is intentionally generic — it does not reveal
    which specific field was incorrect.
    """


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
    Base32-encode 32 raw bytes and split into groups of 4 characters
    separated by hyphens for human-readable display.

    Example: ABCD-EFGH-IJKL-MNOP-...
    """
    b32 = b32encode(raw_bytes).decode("ascii")
    groups = [b32[i:i + 4] for i in range(0, len(b32), 4)]
    return "-".join(groups)


def _parse_recovery_key(recovery_str: str) -> bytes:
    """
    Parse a user-supplied recovery key string: strip hyphens and spaces,
    uppercase, then Base32-decode.

    Raises:
        VaultError: If the string is not valid Base32.
    """
    cleaned = recovery_str.replace("-", "").replace(" ", "").upper()
    try:
        return b32decode(cleaned)
    except Exception:
        raise VaultError("Could not open vault.")


# ---------------------------------------------------------------------------
# Internal: decrypt master key and notes
# ---------------------------------------------------------------------------

def _unwrap_master_key_and_notes(
    fields: dict, wrap_key: bytearray, slot: str
) -> tuple[bytearray, list]:
    """
    Unwrap the master key from the given slot using *wrap_key*, then
    decrypt the notes block.  On failure a generic VaultError is raised —
    the caller cannot tell which field was wrong.

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
        except Exception:
            raise VaultError("Could not open vault.")

        master_key = bytearray(master_key_bytes)

        try:
            # Decrypt the notes block; AAD ensures header integrity is also verified
            aesgcm = AESGCM(bytes(master_key))
            try:
                notes_json = aesgcm.decrypt(
                    fields["notes_nonce"],
                    fields["encrypted_notes"],
                    fields["aad"],
                )
            except Exception:
                raise VaultError("Could not open vault.")
            notes = _json_to_notes(notes_json)
        except VaultError:
            raise
        except Exception:
            raise VaultError("Could not open vault.")

        return master_key, notes

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
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    # 1. Master key: 32 random bytes
    master_key = bytearray(os.urandom(HASH_LENGTH))

    try:
        # 2a. Password slot: Argon2id → wrap key → AES-GCM
        password_salt = os.urandom(PASSWORD_SALT_LENGTH)
        password_bytes = password.encode("utf-8")
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

        # 3. Encrypt the empty notes list with the master key.
        #    Strategy: generate notes_nonce first, build the header (= AAD),
        #    then encrypt so the AAD is known before encryption.
        notes_nonce = os.urandom(NONCE_LENGTH)

        # Build a temporary vault to derive the AAD (encrypted_notes placeholder = b"")
        _tmp = _pack_vault(
            DEFAULT_MEMORY_COST, DEFAULT_TIME_COST, DEFAULT_PARALLELISM,
            password_salt, password_nonce, password_ciphertext,
            recovery_salt, recovery_nonce, recovery_ciphertext,
            notes_nonce, b"",
        )
        aad = _tmp[:_HEADER_SIZE]

        aesgcm = AESGCM(bytes(master_key))
        encrypted_notes = aesgcm.encrypt(notes_nonce, _notes_to_json([]), aad)

        # 4. Pack the final vault bytes
        vault_bytes = _pack_vault(
            DEFAULT_MEMORY_COST, DEFAULT_TIME_COST, DEFAULT_PARALLELISM,
            password_salt, password_nonce, password_ciphertext,
            recovery_salt, recovery_nonce, recovery_ciphertext,
            notes_nonce, encrypted_notes,
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
        ValueError: Corrupted or unknown format.
        VaultError: Wrong password or corrupted data.
    """
    fields = _unpack_vault(vault_bytes)
    password_bytes = password.encode("utf-8")
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


def save_notes(vault_bytes: bytes, master_key: bytearray, notes: list) -> bytes:
    """
    Re-encrypt the notes list with a fresh nonce and return updated vault bytes.

    The master key and both key slots are unchanged; only the notes block
    is re-encrypted.  A new nonce is mandatory on every save.

    Returns:
        Updated vault bytes (new notes nonce).
    """
    fields = _unpack_vault(vault_bytes)

    notes_json = _notes_to_json(notes)

    # Generate a new nonce — reusing the same nonce with the same key is forbidden
    new_notes_nonce = os.urandom(NONCE_LENGTH)

    # Build a temporary vault to compute the new AAD (notes_nonce is part of the header)
    _tmp = _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        fields["password_salt"], fields["password_nonce"], fields["password_ciphertext"],
        fields["recovery_salt"], fields["recovery_nonce"], fields["recovery_ciphertext"],
        new_notes_nonce, b"",
    )
    aad = _tmp[:_HEADER_SIZE]

    aesgcm = AESGCM(bytes(master_key))
    encrypted_notes = aesgcm.encrypt(new_notes_nonce, notes_json, aad)

    return _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        fields["password_salt"], fields["password_nonce"], fields["password_ciphertext"],
        fields["recovery_salt"], fields["recovery_nonce"], fields["recovery_ciphertext"],
        new_notes_nonce, encrypted_notes,
    )


def change_password(
    vault_bytes: bytes, master_key: bytearray, new_password: str
) -> bytes:
    """
    Replace the password slot with a new salt and new encryption.
    The notes block is re-encrypted under the new AAD (because the header
    includes the password slot).  The recovery slot is untouched.

    IMPORTANT: Because the header (= AAD) contains the password slot, changing
    the slot changes the AAD, so the notes block must be re-encrypted.
    That is why master_key is required as a parameter.

    Raises:
        ValueError: New password is too short.
    """
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"New password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    fields = _unpack_vault(vault_bytes)

    # Derive new wrap key from new password
    new_password_salt = os.urandom(PASSWORD_SALT_LENGTH)
    new_password_bytes = new_password.encode("utf-8")
    new_wrap_key = _argon2id_derive(new_password_bytes, new_password_salt)
    try:
        new_password_nonce, new_password_ciphertext = _aesgcm_wrap(
            new_wrap_key, bytes(master_key)
        )
    finally:
        _secure_zero(new_wrap_key)

    # Header changed → re-encrypt the notes block under the new AAD
    old_aesgcm = AESGCM(bytes(master_key))
    notes_json = old_aesgcm.decrypt(
        fields["notes_nonce"],
        fields["encrypted_notes"],
        fields["aad"],
    )

    new_notes_nonce = os.urandom(NONCE_LENGTH)
    _tmp = _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        new_password_salt, new_password_nonce, new_password_ciphertext,
        fields["recovery_salt"], fields["recovery_nonce"], fields["recovery_ciphertext"],
        new_notes_nonce, b"",
    )
    new_aad = _tmp[:_HEADER_SIZE]

    new_aesgcm = AESGCM(bytes(master_key))
    new_encrypted_notes = new_aesgcm.encrypt(new_notes_nonce, notes_json, new_aad)

    return _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        new_password_salt, new_password_nonce, new_password_ciphertext,
        fields["recovery_salt"], fields["recovery_nonce"], fields["recovery_ciphertext"],
        new_notes_nonce, new_encrypted_notes,
    )


def regenerate_recovery_key(
    vault_bytes: bytes, master_key: bytearray
) -> tuple[bytes, str]:
    """
    Replace the recovery slot with a newly generated recovery key.
    The notes block is re-encrypted under the new AAD (because the header
    includes the recovery slot).  The password slot is untouched.

    IMPORTANT: Because the header (= AAD) contains the recovery slot, changing
    the slot changes the AAD, so the notes block must be re-encrypted.

    Returns:
        (new_vault_bytes, new_recovery_key_str)
    """
    fields = _unpack_vault(vault_bytes)

    new_raw_recovery = os.urandom(RECOVERY_KEY_LENGTH)
    new_recovery_salt = os.urandom(RECOVERY_SALT_LENGTH)
    new_wrap_key = _hkdf_derive(new_raw_recovery, new_recovery_salt)
    try:
        new_recovery_nonce, new_recovery_ciphertext = _aesgcm_wrap(
            new_wrap_key, bytes(master_key)
        )
    finally:
        _secure_zero(new_wrap_key)

    # Header changed → re-encrypt the notes block under the new AAD
    old_aesgcm = AESGCM(bytes(master_key))
    notes_json = old_aesgcm.decrypt(
        fields["notes_nonce"],
        fields["encrypted_notes"],
        fields["aad"],
    )

    new_notes_nonce = os.urandom(NONCE_LENGTH)
    _tmp = _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        fields["password_salt"], fields["password_nonce"], fields["password_ciphertext"],
        new_recovery_salt, new_recovery_nonce, new_recovery_ciphertext,
        new_notes_nonce, b"",
    )
    new_aad = _tmp[:_HEADER_SIZE]

    new_aesgcm = AESGCM(bytes(master_key))
    new_encrypted_notes = new_aesgcm.encrypt(new_notes_nonce, notes_json, new_aad)

    new_vault = _pack_vault(
        fields["memory_cost"], fields["time_cost"], fields["parallelism"],
        fields["password_salt"], fields["password_nonce"], fields["password_ciphertext"],
        new_recovery_salt, new_recovery_nonce, new_recovery_ciphertext,
        new_notes_nonce, new_encrypted_notes,
    )
    return new_vault, _format_recovery_key(new_raw_recovery)


def create_note(title: str = "", content: str = "") -> dict:
    """
    Create a new note object.

    Note data model: id (uuid4), title, content, created, modified.
    """
    now = _utc_now_iso()
    return {
        "id":       str(uuid.uuid4()),
        "title":    title,
        "content":  content,
        "created":  now,
        "modified": now,
    }


def update_note(
    note: dict,
    title: str | None = None,
    content: str | None = None,
) -> dict:
    """Update an existing note's title and/or content; refresh the modified timestamp."""
    if title is not None:
        note["title"] = title
    if content is not None:
        note["content"] = content
    note["modified"] = _utc_now_iso()
    return note
