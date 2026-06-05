"""
Persistent token counter with per-day history.
- Stores the current day state in data/tokens.json
- Stores the last 30 days in data/tokens_historial.json
- Separates web vs discord tokens
- Archives the previous day automatically when the date changes
"""
import json
import os
import threading
from datetime import datetime, date
from core.config import TOKENS_FILE

_lock = threading.Lock()
TOKEN_HISTORY_FILE = TOKENS_FILE.replace("tokens.json", "tokens_historial.json")
MAX_HISTORY_DAYS = 30


def _load_state() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as file_handle:
            try:
                return json.load(file_handle)
            except Exception:
                pass
    return _initial_state()


def _initial_state() -> dict:
    return {
        "date": str(date.today()),
        "web": 0,
        "discord": 0,
        "used": 0,
        "limit": 200000,
        "model": "openrouter/free",
        "last_sync": None,
    }


def _save_state(state: dict):
    with _lock:
        with open(TOKENS_FILE, "w") as file_handle:
            json.dump(state, file_handle, ensure_ascii=False, indent=2)


def _load_history() -> list:
    if os.path.exists(TOKEN_HISTORY_FILE):
        with open(TOKEN_HISTORY_FILE) as file_handle:
            try:
                return json.load(file_handle)
            except Exception:
                return []
    return []


def _archive_day(state: dict):
    """Store the current day state in history before resetting it."""
    if state.get("used", 0) == 0:
        return

    history = _load_history()
    entry = {
        "date": state.get("date", str(date.today())),
        "web": state.get("web", 0),
        "discord": state.get("discord", 0),
        "used": state.get("used", 0),
        "model": state.get("model", "openrouter/free"),
    }

    history = [item for item in history if item.get("date") != entry["date"]]
    history.insert(0, entry)
    history = history[:MAX_HISTORY_DAYS]

    with _lock:
        with open(TOKEN_HISTORY_FILE, "w") as file_handle:
            json.dump(history, file_handle, ensure_ascii=False, indent=2)


def add_usage(tokens: int, source: str = "web", model: str = None):
    state = _load_state()

    if state.get("date") != str(date.today()):
        _archive_day(state)
        state = _initial_state()

    if source == "web":
        state["web"] = state.get("web", 0) + tokens
    elif source == "discord":
        state["discord"] = state.get("discord", 0) + tokens

    state["used"] = state.get("web", 0) + state.get("discord", 0)
    if model:
        state["model"] = model
    state["last_sync"] = datetime.now().strftime("%H:%M:%S")
    _save_state(state)


def get_usage() -> dict:
    state = _load_state()

    if state.get("date") != str(date.today()):
        _archive_day(state)
        state = _initial_state()
        _save_state(state)

    limit = state.get("limit", 200000)
    used = state.get("used", 0)
    return {
        "used": used,
        "web": state.get("web", 0),
        "discord": state.get("discord", 0),
        "limit": limit,
        "model": state.get("model", "openrouter/free"),
        "date": state.get("date"),
        "last_sync": state.get("last_sync"),
        "pct": round((used / limit) * 100, 1),
    }


def get_usage_history() -> list:
    """Return previous day history plus today's data."""
    history = _load_history()
    today = get_usage()
    today_entry = {
        "date": today["date"],
        "web": today["web"],
        "discord": today["discord"],
        "used": today["used"],
        "model": today["model"],
        "is_today": True,
    }

    history = [item for item in history if item.get("date") != today["date"]]
    if today["used"] > 0:
        history.insert(0, today_entry)
    return history


def reset_usage():
    _save_state(_initial_state())


def set_model(model: str):
    state = _load_state()
    state["model"] = model
    _save_state(state)
