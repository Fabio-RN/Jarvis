import json
import os
from datetime import datetime
from core.config import ACTIVIDAD_LOG


def record_activity(kind: str, text: str, badge: str = ""):
    """
    kind: 'tool' | 'alert' | 'ok' | 'warn' | 'cmd' | 'auto'
    """
    entry = {
        "type": kind,
        "text": text,
        "badge": badge,
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m/%Y"),
    }
    logs = load_activity()
    logs.insert(0, entry)
    with open(ACTIVIDAD_LOG, "w") as file_handle:
        json.dump(logs[:200], file_handle, ensure_ascii=False)


def load_activity():
    if os.path.exists(ACTIVIDAD_LOG):
        with open(ACTIVIDAD_LOG) as file_handle:
            try:
                return json.load(file_handle)
            except Exception:
                return []
    return []
