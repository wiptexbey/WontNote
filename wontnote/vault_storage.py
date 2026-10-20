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
    4. os.replace() — atomically overwrite the target.
       If power is lost before the rename, the old file is intact.
    5. On Linux, set file permissions to 0o600 and directory to 0o700.

No plaintext backups or leftover temporary copies are ever created.
"""

import os
import sys
import tempfile
from pathlib import Path

from platformdirs import user_data_dir

# Application identifiers used by platformdirs
APP_NAME   = "WontNote"
APP_AUTHOR = "WontNote"

# Vault filename
VAULT_FILENAME = "vault.wnt"


def vault_dir() -> Path:
    """
    Return the platform-appropriate user data directory for WontNote.

    Windows: C:\\Users\\<user>\\AppData\\Local\\WontNote\\WontNote
    Linux:   ~/.local/share/WontNote

    Creates the directory if it does not exist.
    On Linux the directory is chmod'd to 0o700 (owner-only access).
    """
    directory = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    directory.mkdir(parents=True, exist_ok=True)

    # Restrict access on Linux: only the owner can read/write/enter
    if sys.platform != "win32":
        os.chmod(directory, 0o700)

    return directory


def vault_path() -> Path:
    """Return the full path to the vault file."""
    return vault_dir() / VAULT_FILENAME


def vault_exists() -> bool:
    """Return True if the vault file is present on disk."""
    return vault_path().exists()


def read_vault() -> bytes:
    """
    Read the vault file and return its raw bytes.

    Raises:
        FileNotFoundError: Vault file does not exist.
        IOError: Read error.
    """
    path = vault_path()
    if not path.exists():
        raise FileNotFoundError("Vault file not found.")
    return path.read_bytes()


def write_vault(vault_bytes: bytes) -> None:
    """
    Save vault bytes to disk using a safe atomic write.

    Steps:
        - Write to a temporary file in the same directory (same filesystem).
        - flush() + fsync() to ensure data reaches disk.
        - os.replace() for an atomic rename over the target.
        - On Linux, set file permissions to 0o600.

    Raises:
        IOError: Write error.
    """
    directory = vault_dir()
    path      = vault_path()

    # Temporary file must be on the same filesystem as the target
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=directory, suffix=".tmp")
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(vault_bytes)
            f.flush()
            os.fsync(f.fileno())   # Force OS buffers to disk
    except Exception:
        # Clean up the temporary file on failure
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    # On Linux: restrict file permissions to owner read/write only
    if sys.platform != "win32":
        os.chmod(tmp_path, 0o600)

    # Atomic rename — on Windows os.replace() removes an existing target automatically
    os.replace(tmp_path, path)


def delete_vault() -> None:
    """
    Delete the vault file from disk.
    Only used in tests or when the user explicitly resets the vault.
    """
    path = vault_path()
    if path.exists():
        path.unlink()
