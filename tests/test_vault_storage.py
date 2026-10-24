"""
test_vault_storage.py — WontNote Vault Storage Tests
=====================================================
Tests for atomic file writes, backup rotation, error recovery,
and directory isolation.

All tests use pytest's tmp_path fixture to ensure nothing ever touches
the real user data directory.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from wontnote.vault_storage import (
    vault_dir,
    vault_path,
    vault_exists,
    read_vault,
    write_vault,
    delete_vault,
    VAULT_FILENAME,
    BACKUP_FILENAME,
)


def test_storage_never_touches_real_user_data_dir(tmp_path, monkeypatch):
    """
    PROOF OF ISOLATION:
    This test proves that storage operations can be executed with 100% isolation
    from the real user data directory.
    We monkeypatch platformdirs user_data_dir to raise RuntimeError if called.
    When tests specify a custom path (derived from pytest's tmp_path), operations
    succeed cleanly without ever querying platformdirs or touching user directories.
    """
    def forbidden_call(*args, **kwargs):
        raise RuntimeError("CRITICAL: Real user data directory was accessed!")

    monkeypatch.setattr("wontnote.vault_storage.user_data_dir", forbidden_call)

    test_file = tmp_path / VAULT_FILENAME
    write_vault(b"data-1", path=test_file)
    assert read_vault(path=test_file) == b"data-1"
    assert vault_exists(path=test_file) is True

    delete_vault(path=test_file)
    assert vault_exists(path=test_file) is False


def test_backup_contains_previous_vault_bytes_after_second_save(tmp_path):
    """
    Before replacing an existing vault file, write_vault must create vault.wnt.bak
    in the same directory containing the exact previous vault bytes.
    On subsequent saves, vault.wnt.bak must continuously update to the immediately
    prior version.
    """
    v_path = tmp_path / VAULT_FILENAME
    bak_path = tmp_path / BACKUP_FILENAME

    data_v1 = b"ENCRYPTED_VAULT_BYTES_VERSION_1"
    data_v2 = b"ENCRYPTED_VAULT_BYTES_VERSION_2"
    data_v3 = b"ENCRYPTED_VAULT_BYTES_VERSION_3"

    # First save: creates vault.wnt; no backup should exist yet
    write_vault(data_v1, path=v_path)
    assert v_path.exists()
    assert v_path.read_bytes() == data_v1
    assert not bak_path.exists()

    # Second save: vault.wnt gets data_v2, vault.wnt.bak gets data_v1
    write_vault(data_v2, path=v_path)
    assert v_path.read_bytes() == data_v2
    assert bak_path.exists()
    assert bak_path.read_bytes() == data_v1

    # Third save: vault.wnt gets data_v3, vault.wnt.bak gets data_v2
    write_vault(data_v3, path=v_path)
    assert v_path.read_bytes() == data_v3
    assert bak_path.read_bytes() == data_v2


def test_atomic_write_error_simulation(tmp_path):
    """
    Moved from test_crypto_core.py using tmp_path without monkeypatching vault_dir/vault_path.
    If writing to the temporary file fails, the existing vault file must
    remain intact and no leftover .tmp file should be present.
    """
    v_path = tmp_path / VAULT_FILENAME
    original_data = b"ORIGINAL_VALID_VAULT_DATA"
    write_vault(original_data, path=v_path)

    original_fdopen = os.fdopen

    def failing_fdopen(fd, mode):
        f = original_fdopen(fd, mode)

        class FailingFile:
            def write(self, data):
                raise IOError("Simulated disk write failure")
            def flush(self):
                f.flush()
            def fileno(self):
                return f.fileno()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                f.close()

        return FailingFile()

    with patch("os.fdopen", side_effect=failing_fdopen):
        with pytest.raises(IOError):
            write_vault(b"CORRUPT_DATA", path=v_path)

    assert read_vault(path=v_path) == original_data
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_write_failure_after_backup_leaves_backup_and_original_intact(tmp_path):
    """
    os.fdopen fails ONLY on the second call (the main vault temp write,
    after the backup write succeeded).
    Assert:
    - original vault is unchanged
    - vault.wnt.bak contains the original bytes
    - no *.tmp files remain
    """
    v_path = tmp_path / VAULT_FILENAME
    bak_path = tmp_path / BACKUP_FILENAME
    original_data = b"ORIGINAL_VAULT_BYTES"
    write_vault(original_data, path=v_path)

    original_fdopen = os.fdopen
    fdopen_calls = [0]

    def fdopen_fail_on_second(fd, mode):
        fdopen_calls[0] += 1
        if fdopen_calls[0] == 2:
            class FailingFile:
                def write(self, data):
                    raise IOError("Simulated failure on main vault write")
                def flush(self):
                    pass
                def fileno(self):
                    return fd
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    os.close(fd)
            return FailingFile()
        return original_fdopen(fd, mode)

    with patch("os.fdopen", side_effect=fdopen_fail_on_second):
        with pytest.raises(IOError):
            write_vault(b"NEW_DATA", path=v_path)

    assert read_vault(path=v_path) == original_data
    assert bak_path.exists()
    assert bak_path.read_bytes() == original_data
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_write_failure_on_os_replace_leaves_original_intact(tmp_path, monkeypatch):
    """
    If os.replace raises OSError:
    - original vault intact
    - no *.tmp remains
    """
    v_path = tmp_path / VAULT_FILENAME
    original_data = b"ORIGINAL_VAULT_BYTES"
    write_vault(original_data, path=v_path)

    def failing_replace(src, dst):
        raise OSError("Simulated filesystem error during replace")

    monkeypatch.setattr("os.replace", failing_replace)

    with pytest.raises(OSError):
        write_vault(b"NEW_DATA", path=v_path)

    assert read_vault(path=v_path) == original_data
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_permission_error_exhaustion_raises_and_cleans_tmp(tmp_path, monkeypatch):
    """
    When os.replace raises PermissionError on all 5 attempts on Windows:
    - PermissionError is raised
    - no *.tmp files remain
    """
    v_path = tmp_path / VAULT_FILENAME
    attempts = [0]

    def always_locked_replace(src, dst):
        attempts[0] += 1
        raise PermissionError("File permanently locked")

    monkeypatch.setattr("os.replace", always_locked_replace)
    monkeypatch.setattr(sys, "platform", "win32")

    with pytest.raises(PermissionError):
        write_vault(b"SOME_DATA", path=v_path)

    assert attempts[0] == 5
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_read_nonexistent_vault_raises_file_not_found(tmp_path):
    """Attempting to read a non-existent vault path must raise FileNotFoundError."""
    missing_path = tmp_path / "nonexistent_vault.wnt"
    with pytest.raises(FileNotFoundError, match="not found"):
        read_vault(path=missing_path)


def test_delete_vault_removes_both_vault_and_backup(tmp_path):
    """delete_vault must remove both the vault file and the backup file if present."""
    v_path = tmp_path / VAULT_FILENAME
    bak_path = tmp_path / BACKUP_FILENAME

    write_vault(b"v1", path=v_path)
    write_vault(b"v2", path=v_path)
    assert v_path.exists()
    assert bak_path.exists()

    delete_vault(path=v_path)
    assert not v_path.exists()
    assert not bak_path.exists()


def test_windows_permission_error_retry(tmp_path, monkeypatch):
    """
    Simulate temporary PermissionError during os.replace (e.g. Windows file locking
    by antivirus/indexer). The write should retry and succeed once the lock clears.
    """
    v_path = tmp_path / VAULT_FILENAME
    attempts = [0]
    real_replace = os.replace

    def flaky_replace(src, dst):
        attempts[0] += 1
        if attempts[0] <= 2:
            raise PermissionError("Simulated temporary lock")
        return real_replace(src, dst)

    monkeypatch.setattr("os.replace", flaky_replace)
    monkeypatch.setattr(sys, "platform", "win32")

    write_vault(b"RETRY_SUCCESS_DATA", path=v_path)
    assert attempts[0] == 3
    assert read_vault(path=v_path) == b"RETRY_SUCCESS_DATA"


def test_write_vault_keep_backup_false_removes_existing_backup(tmp_path):
    """
    When keep_backup=False:
    - No new .bak is created
    - Any pre-existing vault.wnt.bak is removed
    """
    v_path = tmp_path / VAULT_FILENAME
    bak_path = tmp_path / BACKUP_FILENAME

    # First write
    write_vault(b"v1", path=v_path, keep_backup=True)
    # Second write with backup -> backup exists
    write_vault(b"v2", path=v_path, keep_backup=True)
    assert bak_path.exists()
    assert bak_path.read_bytes() == b"v1"

    # Third write with keep_backup=False
    write_vault(b"v3", path=v_path, keep_backup=False)
    assert read_vault(path=v_path) == b"v3"
    assert not bak_path.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file permissions only")
def test_posix_permissions(tmp_path):
    """
    On POSIX systems:
    - A pre-existing directory with mode 0o755 keeps 0o755 after write_vault.
    - A newly created directory via vault_dir gets 0o700.
    - The vault file gets 0o600.
    """
    # 1. Pre-existing directory with 0o755
    pre_dir = tmp_path / "pre_existing_dir"
    pre_dir.mkdir(mode=0o755)
    os.chmod(pre_dir, 0o755)
    pre_vault = pre_dir / VAULT_FILENAME

    write_vault(b"data", path=pre_vault)
    assert (pre_dir.stat().st_mode & 0o777) == 0o755
    assert (pre_vault.stat().st_mode & 0o777) == 0o600

    # 2. Newly created directory via vault_dir
    new_dir = tmp_path / "new_vault_dir"
    created_dir = vault_dir(custom_dir=new_dir)
    assert (created_dir.stat().st_mode & 0o777) == 0o700


def test_user_data_dir_called_with_appauthor_false(monkeypatch):
    """
    Verify platformdirs user_data_dir is called with appauthor=False so Windows path
    does not duplicate the app author name (i.e. Local\\WontNote instead of Local\\WontNote\\WontNote).
    """
    captured_kwargs = {}

    def spy_user_data_dir(appname, *args, **kwargs):
        captured_kwargs["appname"] = appname
        captured_kwargs.update(kwargs)
        return "dummy/path/wontnote"

    monkeypatch.setattr("wontnote.vault_storage.user_data_dir", spy_user_data_dir)
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: None)
    monkeypatch.setattr(Path, "exists", lambda self: True)

    vault_dir()

    assert captured_kwargs.get("appname") == "WontNote"
    assert captured_kwargs.get("appauthor") is False
