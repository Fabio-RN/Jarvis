import requests
from core.config import (
    JELLYSEERR_URL, JELLYSEERR_KEY,
    RADARR_URL, RADARR_KEY,
    SONARR_URL, SONARR_KEY
)


# ── Jellyseerr ───────────────────────────────────────────────────────
def jellyseerr_search(query):
    try:
        r = requests.get(f"{JELLYSEERR_URL}/api/v1/search",
            params={"query": query, "language": "es"},
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        results = r.json().get("results", [])[:5]
        if not results:
            return "No results found."
        out = []
        for item in results:
            media_type = item.get("mediaType", "")
            title  = item.get("title") or item.get("name", "")
            year   = (item.get("releaseDate") or item.get("firstAirDate") or "")[:4]
            status = item.get("mediaInfo", {}).get("status", 0)
            statuses = {1: "✅ Available", 2: "⏳ Pending", 3: "⏳ Processing", 4: "⏳ Partial", 5: "✅ Available"}
            out.append(f"{title} ({year}) [{media_type}] — {statuses.get(status, '❌ Unavailable')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyseerr: {e}"


def jellyseerr_pending_requests():
    try:
        r = requests.get(f"{JELLYSEERR_URL}/api/v1/request",
            params={"filter": "pending", "take": 10},
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        items = r.json().get("results", [])
        if not items:
            return "No pending requests."
        out = []
        for item in items:
            media       = item.get("media", {})
            title       = media.get("originalTitle") or media.get("originalName") or "Unknown"
            requester   = item.get("requestedBy", {}).get("displayName", "?")
            out.append(f"ID:{item['id']} — {title} (requested by {requester})")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyseerr: {e}"


def jellyseerr_approve(request_id):
    try:
        r = requests.post(f"{JELLYSEERR_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        return f"Request {request_id} approved." if r.status_code == 200 else f"Error: {r.status_code}"
    except Exception as e:
        return f"Error Jellyseerr: {e}"


# ── Radarr ───────────────────────────────────────────────────────────
def radarr_search(query):
    try:
        r = requests.get(f"{RADARR_URL}/api/v3/movie/lookup",
            params={"term": query},
            headers={"X-Api-Key": RADARR_KEY}, timeout=10)
        results = r.json()[:5]
        if not results:
            return "No movies found."
        out = []
        for m in results:
            status = "✅ In library" if m.get("hasFile") else "❌ Not downloaded"
            out.append(f"{m['title']} ({m.get('year','?')}) — {status}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Radarr: {e}"


def radarr_status():
    try:
        r = requests.get(f"{RADARR_URL}/api/v3/movie",
            headers={"X-Api-Key": RADARR_KEY}, timeout=10)
        movies     = r.json()
        total      = len(movies)
        downloaded = sum(1 for m in movies if m.get("hasFile"))
        return f"Total: {total} | Downloaded: {downloaded} | Missing: {total - downloaded}"
    except Exception as e:
        return f"Error Radarr: {e}"


# ── Sonarr ───────────────────────────────────────────────────────────
def sonarr_search(query):
    try:
        r = requests.get(f"{SONARR_URL}/api/v3/series/lookup",
            params={"term": query},
            headers={"X-Api-Key": SONARR_KEY}, timeout=10)
        results = r.json()[:5]
        if not results:
            return "No series found."
        out = []
        for s in results:
            out.append(f"{s['title']} — {s.get('seasonCount',0)} seasons — {s.get('status','?')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Sonarr: {e}"


def sonarr_status():
    try:
        r = requests.get(f"{SONARR_URL}/api/v3/series",
            headers={"X-Api-Key": SONARR_KEY}, timeout=10)
        return f"Total series: {len(r.json())}"
    except Exception as e:
        return f"Error Sonarr: {e}"
