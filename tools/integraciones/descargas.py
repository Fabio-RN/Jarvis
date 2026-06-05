import requests
from core.config import QBIT_URL, QBIT_USER, QBIT_PASS


def _login():
    session = requests.Session()
    session.post(f"{QBIT_URL}/api/v2/auth/login",
        data={"username": QBIT_USER, "password": QBIT_PASS})
    return session


def qbit_estado():
    try:
        session = _login()
        torrents = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10).json()
        if not torrents:
            return "No active torrents."
        out = []
        for t in torrents[:10]:
            progreso = round(t.get("progress", 0) * 100, 1)
            out.append(f"{t.get('name','?')[:40]} — {progreso}% — {t.get('state','?')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error qBit: {e}"


def qbit_pausar(nombre):
    try:
        session = _login()
        torrents = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10).json()
        for t in torrents:
            if nombre.lower() in t.get("name", "").lower():
                session.post(f"{QBIT_URL}/api/v2/torrents/pause", data={"hashes": t["hash"]})
                return f"Torrent '{t['name']}' paused."
        return "Torrent not found."
    except Exception as e:
        return f"Error qBit: {e}"


def qbit_reanudar(nombre):
    try:
        session = _login()
        torrents = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10).json()
        for t in torrents:
            if nombre.lower() in t.get("name", "").lower():
                session.post(f"{QBIT_URL}/api/v2/torrents/resume", data={"hashes": t["hash"]})
                return f"Torrent '{t['name']}' resumed."
        return "Torrent not found."
    except Exception as e:
        return f"Error qBit: {e}"
