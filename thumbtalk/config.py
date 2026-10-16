"""Settings and word list, stored per user in %APPDATA%\\ThumbTalk (never inside the install folder)."""
import json, os, shutil

APP = "ThumbTalk"
VERSION = "0.1.0"
HOME_URL = "https://github.com/VW3st/thumbtalk"
DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP)
os.makedirs(DIR, exist_ok=True)
SETTINGS_F = os.path.join(DIR, "settings.json")
WORDS_F = os.path.join(DIR, "words.json")
LOG_F = os.path.join(DIR, "thumbtalk.log")
DEFAULT_WORDS_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_words.json")

DEFAULTS = {
    "trigger": "mouse_back",   # see trigger.TRIGGERS
    "hold_secs": 0.25,         # a shorter press is passed through as a normal click
    "model": "auto",           # auto | large-v3-turbo | small | base
    "language": "en",          # en | auto
    "cleanup_model": "off",    # off | any local Ollama model name
    "cmd_send": True,          # "send it" presses Enter
    "cmd_newline": True,       # "new line" / "new paragraph"
    "cmd_scratch": True,       # "scratch that"
    "paused": False,
    "pos": "bottom-center",    # a preset name, or [x, y] after dragging
    "first_run": True,
}


def _load(path, default):
    try:
        with open(path, encoding="utf-8-sig") as f:   # -sig: tolerate files saved by Notepad/PowerShell with a BOM
            return {**default, **json.load(f)}
    except Exception:
        return dict(default)


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


S = _load(SETTINGS_F, DEFAULTS)
W = {"vocab": [], "fix": {}}   # mutated in place so every module sees updates


def save_settings():
    _save(SETTINGS_F, S)


def load_words():
    if not os.path.exists(WORDS_F):
        shutil.copy(DEFAULT_WORDS_F, WORDS_F)
    W.clear()
    W.update(_load(WORDS_F, {"vocab": [], "fix": {}}))


def save_words():
    _save(WORDS_F, W)


load_words()
