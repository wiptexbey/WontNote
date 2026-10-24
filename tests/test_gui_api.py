"""Regression checks for bridge persistence and locked-vault protection."""
from copy import deepcopy
import pytest
from wontnote.gui.api import WontNoteAPI


def opened_api(monkeypatch):
    api = WontNoteAPI()
    api._master_key = bytearray(b"x" * 32)
    api._vault_bytes = b"encrypted-vault"
    monkeypatch.setattr(api, "_persist", lambda: None)
    return api


@pytest.mark.parametrize("method,args", [
    ("create_note", ()), ("save_note", ({"id": "missing"},)),
    ("delete_note", ("missing",)), ("toggle_pin", ("missing",)),
    ("restore_note", ("missing",)), ("change_password", ("old", "new-password-long")),
])
def test_locked_vault_rejects_mutations(method, args):
    api = WontNoteAPI()
    assert getattr(api, method)(*args)["success"] is False
    assert api._notes == []


def test_font_preferences_persist_on_existing_note(monkeypatch):
    api = opened_api(monkeypatch)
    note = api.create_note()["note"]
    result = api.save_note({"id": note["id"], "font": "georgia", "font_size": 20})
    assert result["success"]
    assert result["note"]["font"] == "georgia"
    assert result["note"]["font_size"] == 20


def test_failed_write_rolls_back_note_changes(monkeypatch):
    api = opened_api(monkeypatch)
    note = api.create_note()["note"]
    previous = deepcopy(api._notes)
    def fail():
        raise OSError("disk full")
    monkeypatch.setattr(api, "_persist", fail)
    assert not api.save_note({"id": note["id"], "title": "unsaved"})["success"]
    assert api._notes == previous
    assert not api.create_note()["success"]
    assert api._notes == previous


def test_delayed_save_cannot_resurrect_deleted_note(monkeypatch):
    api = opened_api(monkeypatch)
    note = api.create_note()["note"]
    api.delete_note(note["id"], permanent=True)
    assert not api.save_note(note)["success"]
    assert api._notes == []
