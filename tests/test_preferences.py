import pytest
from wontnote.gui import preferences


@pytest.fixture
def preferences_file(tmp_path,monkeypatch):
    path=tmp_path / "preferences.json"
    monkeypatch.setattr(preferences,"_path",lambda:path)
    return path


def test_settings_survive_new_session(preferences_file):
    preferences.save_preference("wn_auto_lock","5")
    preferences.save_preference("wn_theme","rose")
    assert preferences.read_preferences()=={"wn_auto_lock":"5","wn_theme":"rose"}


@pytest.mark.parametrize("key,value",[("password","secret"),("wn_auto_lock","-5"),("wn_font","<script>"),("wn_theme","dark")])
def test_secrets_and_invalid_values_cannot_be_saved(preferences_file,key,value):
    with pytest.raises(ValueError):preferences.save_preference(key,value)
    assert not preferences_file.exists()


def test_corrupt_settings_fall_back_without_affecting_vault(preferences_file):
    preferences_file.write_text("not json")
    assert preferences.read_preferences()=={}
