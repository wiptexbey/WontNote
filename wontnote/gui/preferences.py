"""Persist only validated, non-secret preferences; keep WebView private mode."""
import json
import re
from wontnote.vault_storage import vault_dir, _atomic_write_file

OPTIONS = {
    "wn_theme": {"light","sage","ocean","rose","sand"},
    "wn_autosave": {"300","800","1500"},
    "wn_line_height": {"1.6","1.9","2.2"},
    "wn_auto_lock": {"0","1","5","15","30"},
    **{key: {"true","false"} for key in ("wn_spellcheck","wn_word_count","wn_lock_minimize","wn_compact","wn_reduce_motion")},
}


def _path():
    return vault_dir() / "preferences.json"


def valid_preference(key, value):
    if not isinstance(key,str) or not isinstance(value,str):
        return False
    if key == "wn_font":
        return bool(re.fullmatch(r"[A-Za-z]{1,24}",value))
    return key in OPTIONS and value in OPTIONS[key]


def read_preferences():
    try:
        path=_path()
        if path.stat().st_size > 16384:
            return {}
        data=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data,dict):
            return {}
        return {key:value for key,value in data.items() if valid_preference(key,value)}
    except (OSError,ValueError,TypeError):
        return {}


def save_preference(key,value):
    if not valid_preference(key,value):
        raise ValueError("Geçersiz tercih.")
    data=read_preferences();data[key]=value
    _atomic_write_file(_path(),json.dumps(data,ensure_ascii=False).encode("utf-8"))
