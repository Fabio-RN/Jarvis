import requests
from core.config import JELLYFIN_URL, JELLYFIN_KEY


def jellyfin_connected_users():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Sessions",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        sessions = [s for s in r.json() if s.get("NowPlayingItem")]
        if not sessions:
            return "No users playing content right now."
        out = []
        for s in sessions:
            out.append(f"{s.get('UserName','?')} → {s.get('NowPlayingItem',{}).get('Name','?')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyfin: {e}"


def jellyfin_library_status():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Items/Counts",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        d = r.json()
        return f"Movies: {d.get('MovieCount',0)} | Series: {d.get('SeriesCount',0)} | Episodes: {d.get('EpisodeCount',0)}"
    except Exception as e:
        return f"Error Jellyfin: {e}"
