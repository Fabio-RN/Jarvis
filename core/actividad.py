import json
import os
from datetime import datetime
from core.config import ACTIVITY_LOG


def log(entry_type: str, text: str, badge: str = ""):
    """
    entry_type: 'tool' | 'alert' | 'ok' | 'warn' | 'cmd' | 'auto'
    """
    entry = {
        "type": entry_type,
        "text": text,
        "badge": badge,
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m/%Y")
    }
    entries = load()
    entries.insert(0, entry)
    with open(ACTIVITY_LOG, "w") as f:
        json.dump(entries[:200], f, ensure_ascii=False)


def load():
    if os.path.exists(ACTIVITY_LOG):
        with open(ACTIVITY_LOG) as f:
            try:
                return json.load(f)
            except:
                return []
    return []
