"""
Persistent token counter with per-day history.
- Saves to data/tokens.json (current day state)
- Saves to data/tokens_history.json (last 30 days)
- Separates web vs discord tokens
- Archives previous day automatically when the day changes
"""
import json
import os
import threading
from datetime import datetime, date
from core.config import TOKENS_FILE

_lock          = threading.Lock()
HISTORY_FILE = TOKENS_FILE.replace("tokens.json", "tokens_history.json")
MAX_DAYS      = 30


def _load() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            try:
                return json.load(f)
            except:
                pass
    return _initial_state()


def _initial_state() -> dict:
    return {
        "date":       str(date.today()),
        "web":        0,
        "discord":    0,
        "total":      0,
        "limit":      200000,
        "model":      "openrouter/free",
        "last_sync": None,
    }


def _save(state: dict):
    with _lock:
        with open(TOKENS_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


def _archive_day(state: dict):
    if state.get("total", 0) == 0:
        return

    history = _load_history()

    entry = {
        "date":   state.get("date", str(date.today())),
        "web":    state.get("web", 0),
        "discord": state.get("discord", 0),
        "total":  state.get("total", 0),
        "model":  state.get("model", "openrouter/free"),
    }

    history = [h for h in history if h.get("date") != entry["date"]]
    history.insert(0, entry)
    history = history[:MAX_DAYS]

    with _lock:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


def _load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def add(tokens: int, origin: str = "web", model: str = None):
    state = _load()

    if state.get("date") != str(date.today()):
        _archive_day(state)
        state = _initial_state()

    if origin == "web":
        state["web"]     = state.get("web", 0) + tokens
    elif origin == "discord":
        state["discord"] = state.get("discord", 0) + tokens

    state["total"]       = state.get("web", 0) + state.get("discord", 0)
    if model:
        state["model"]  = model
    state["last_sync"] = datetime.now().strftime("%H:%M:%S")
    _save(state)


def get() -> dict:
    state = _load()

    if state.get("date") != str(date.today()):
        _archive_day(state)
        state = _initial_state()
        _save(state)

    return {
        "used":      state.get("total", 0),
        "web":       state.get("web", 0),
        "discord":   state.get("discord", 0),
        "total":     state.get("limit", 200000),
        "model":     state.get("model", "openrouter/free"),
        "date":      state.get("date"),
        "last_sync": state.get("last_sync"),
        "pct":       round((state.get("total", 0) / state.get("limit", 200000)) * 100, 1),
    }


def get_history() -> list:
    history = _load_history()
    today   = get()

    today_entry = {
        "date":   today["date"],
        "web":    today["web"],
        "discord": today["discord"],
        "total":  today["used"],
        "model":  today["model"],
        "is_today": True,
    }

    history = [h for h in history if h.get("date") != today["date"]]

    if today["used"] > 0:
        history.insert(0, today_entry)

    return history


def reset():
    state = _initial_state()
    _save(state)


def set_model(model: str):
    state = _load()
    state["model"] = model
    _save(state)
