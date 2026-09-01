"""
Conversation history with per-origin support.
- web      → history_web.json
- discord  → history_discord.json
- dm       → history_dm.json
- (empty)  → historial.json  ← legacy
"""
import json
import os
from core.config import DATA_DIR

MAX_TURNS = 200
MAX_RECENT = 20

_FILES = {
    "web":     os.path.join(DATA_DIR, "history_web.json"),
    "discord": os.path.join(DATA_DIR, "history_discord.json"),
    "dm":      os.path.join(DATA_DIR, "history_dm.json"),
    "":        os.path.join(DATA_DIR, "historial.json"),
}


def _file(origin: str = "") -> str:
    return _FILES.get(origin, _FILES[""])


def load(origin: str = "") -> list:
    path = _file(origin)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return []


def save(history: list, origin: str = ""):
    path = _file(origin)
    with open(path, "w") as f:
        json.dump(history[-MAX_TURNS:], f, ensure_ascii=False, indent=2)


def add(history: list, role: str, content: str, origin: str = "") -> list:
    history = history + [{"role": role, "content": content}]
    save(history, origin)
    return history


def recent(history: list) -> list:
    return history[-MAX_RECENT:]


def clear(origin: str = "") -> list:
    save([], origin)
    return []
