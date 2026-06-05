import requests
from core.config import JELLYFIN_URL, JELLYFIN_KEY


def jellyfin_usuarios_conectados():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Sessions",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        sesiones = [s for s in r.json() if s.get("NowPlayingItem")]
        if not sesiones:
            return "No users are playing content right now."
        out = []
        for s in sesiones:
            out.append(f"{s.get('UserName','?')} → {s.get('NowPlayingItem',{}).get('Name','?')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyfin: {e}"


def jellyfin_estado_biblioteca():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Items/Counts",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        d = r.json()
        return f"Movies: {d.get('MovieCount',0)} | Series: {d.get('SeriesCount',0)} | Episodes: {d.get('EpisodeCount',0)}"
    except Exception as e:
        return f"Error Jellyfin: {e}"
