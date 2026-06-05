"""
Conversation history with separate source support.
- web      -> historial_web.json
- discord  -> historial_discord.json
- dm       -> historial_dm.json
- (empty)  -> historial.json  <- compatibility with legacy code
"""
import json
import os
from core.config import DATA_DIR

MAX_STORED_TURNS = 200
MAX_RECENT_TURNS = 20

_HISTORY_FILES = {
    "web":     os.path.join(DATA_DIR, "historial_web.json"),
    "discord": os.path.join(DATA_DIR, "historial_discord.json"),
    "dm":      os.path.join(DATA_DIR, "historial_dm.json"),
    "":        os.path.join(DATA_DIR, "historial.json"),
}


def _history_file(source: str = "") -> str:
    return _HISTORY_FILES.get(source, _HISTORY_FILES[""])


def load_history(source: str = "") -> list:
    """Load history for the given source from disk."""
    path = _history_file(source)
    if os.path.exists(path):
        try:
            with open(path) as file_handle:
                return json.load(file_handle)
        except Exception:
            pass
    return []


def save_history(history: list, source: str = ""):
    """Persist history to disk, truncating it to MAX_STORED_TURNS."""
    path = _history_file(source)
    with open(path, "w") as file_handle:
        json.dump(history[-MAX_STORED_TURNS:], file_handle, ensure_ascii=False, indent=2)


def append_history_turn(history: list, role: str, content: str, source: str = "") -> list:
    """
    Add a turn to the history, persist it, and return the updated list.
    role: 'user' | 'assistant'
    """
    history = history + [{"role": role, "content": content}]
    save_history(history, source)
    return history


def recent_history(history: list) -> list:
    """Return only the latest MAX_RECENT_TURNS turns to send to the model."""
    return history[-MAX_RECENT_TURNS:]


def clear_history(source: str = "") -> list:
    """Clear history for the source and return an empty list."""
    save_history([], source)
    return []
