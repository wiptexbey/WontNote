"""Passwordless attack regressions. All vault files are isolated test fixtures."""
import pytest
from wontnote.gui.api import WontNoteAPI
import wontnote.gui.api as bridge
from wontnote.crypto_core import create_vault, unlock_with_password, VaultError, _secure_zero


@pytest.fixture
def stored_vault(tmp_path, monkeypatch):
    path=tmp_path / "vault.wnt"
    data,_=create_vault("test-password-12345")
    path.write_bytes(data)
    monkeypatch.setattr(bridge,"read_vault",lambda: path.read_bytes())
    monkeypatch.setattr(bridge,"vault_path",lambda: path)
    monkeypatch.setattr(bridge,"write_vault",lambda data,**kwargs: path.write_bytes(data))
    return path


def test_passwordless_create_cannot_replace_existing_vault(stored_vault):
    original=stored_vault.read_bytes()
    result=WontNoteAPI().create_vault("attacker-password-123")
    assert not result["success"]
    assert stored_vault.read_bytes()==original


def test_passwordless_reset_cannot_delete_locked_vault(stored_vault):
    original=stored_vault.read_bytes()
    result=WontNoteAPI().reset_vault()
    assert not result["success"]
    assert stored_vault.read_bytes()==original


def test_bad_password_never_releases_notes(stored_vault):
    api=WontNoteAPI()
    for password in ("", "wrong-password", "' OR 1=1 --", "test-password-1234"):
        result=api.unlock_password(password)
        assert not result["success"]
        assert "notes" not in result
        assert api.get_notes()==[]


def test_lock_revokes_all_note_access(stored_vault):
    api=WontNoteAPI()
    assert api.unlock_password("test-password-12345")["success"]
    assert api.create_note()["success"]
    api.lock()
    assert api.get_notes()==[]
    for method,args in [("create_note",()),("save_note",({"id":"missing","content":"attack"},)),("delete_note",("missing",)),("regenerate_recovery_key",())]:
        assert not getattr(api,method)(*args)["success"]


def test_ciphertext_tampering_cannot_unlock(stored_vault):
    data=bytearray(stored_vault.read_bytes()); data[-1]^=1
    stored_vault.write_bytes(data)
    assert not WontNoteAPI().unlock_password("test-password-12345")["success"]


def test_rate_limit_covers_password_and_recovery(stored_vault,monkeypatch):
    api=WontNoteAPI();now=[100.0];api._clock=lambda:now[0]
    for _ in range(5):assert not api.unlock_password("wrong")["success"]
    # Even a correct credential is delayed while the online limiter is active.
    blocked=api.unlock_password("test-password-12345")
    assert blocked["retry_seconds"]==5
    assert api.unlock_recovery("invalid")["retry_seconds"]==5
    now[0]+=6
    assert api.unlock_password("test-password-12345")["success"]


def test_reset_requires_password_and_explicit_confirmation(stored_vault):
    api=WontNoteAPI();original=stored_vault.read_bytes()
    assert not api.reset_vault("", "ONAYLIYORUM")["success"]
    assert not api.reset_vault("wrong", "ONAYLIYORUM")["success"]
    assert not api.reset_vault("test-password-12345", "")["success"]
    assert stored_vault.read_bytes()==original
    assert api.reset_vault("test-password-12345", "ONAYLIYORUM")["success"]
    assert not stored_vault.exists()


def test_get_notes_cannot_mutate_internal_state(stored_vault):
    api=WontNoteAPI();api.unlock_password("test-password-12345");api.create_note()
    notes=api.get_notes();notes[0]["title"]="outside mutation"
    assert api.get_notes()[0]["title"]!="outside mutation"


def test_bad_payload_cannot_poison_note_list(stored_vault):
    api=WontNoteAPI();api.unlock_password("test-password-12345")
    note=api.create_note()["note"]
    assert not api.save_note({"id":note["id"],"title":{"attack":"payload"}})["success"]
    assert isinstance(api.get_notes()[0]["title"],str)


def test_recovery_without_secret_fails(stored_vault):
    api=WontNoteAPI()
    for key in ("", "AAAA-AAAA", "A"*52):
        assert not api.unlock_recovery(key)["success"]
        assert api.get_notes()==[]


def test_tampered_header_cannot_force_gigabyte_allocation(stored_vault,monkeypatch):
    import struct
    data=bytearray(stored_vault.read_bytes());struct.pack_into(">I",data,5,1048576);stored_vault.write_bytes(data)
    called=[]
    monkeypatch.setattr(bridge,"unlock_with_password",lambda *args:called.append(True))
    assert not WontNoteAPI().unlock_password("anything")["success"]
    assert called==[]


def test_unlock_cannot_race_a_lock_and_resurrect_session(stored_vault,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    original=bridge.unlock_with_password
    entered,release=Event(),Event()
    def slow_unlock(*args):
        entered.set();assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(bridge,"unlock_with_password",slow_unlock)
    api=WontNoteAPI()
    with ThreadPoolExecutor(max_workers=2) as pool:
        unlocking=pool.submit(api.unlock_password,"test-password-12345")
        assert entered.wait(5)
        locking=pool.submit(api.lock)
        release.set()
        assert unlocking.result()["success"]
        assert locking.result()["success"]
    assert api._master_key is None
    assert api.get_notes()==[]


def test_atomic_creation_never_overwrites_existing_vault(tmp_path):
    from wontnote.vault_storage import write_new_vault
    path=tmp_path / "vault.wnt"
    write_new_vault(b"first encrypted vault",path)
    with pytest.raises(FileExistsError):
        write_new_vault(b"attacker replacement",path)
    assert path.read_bytes()==b"first encrypted vault"
    assert list(tmp_path.glob("*.tmp"))==[]
