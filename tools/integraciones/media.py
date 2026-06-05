import requests
from core.config import (
    JELLYSEERR_URL, JELLYSEERR_KEY,
    RADARR_URL, RADARR_KEY,
    SONARR_URL, SONARR_KEY
)


# ── Jellyseerr ───────────────────────────────────────────────────────
def jellyseerr_buscar(query):
    try:
        r = requests.get(f"{JELLYSEERR_URL}/api/v1/search",
            params={"query": query, "language": "es"},
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        resultados = r.json().get("results", [])[:5]
        if not resultados:
            return "No results found."
        out = []
        for item in resultados:
            tipo    = item.get("mediaType", "")
            titulo  = item.get("title") or item.get("name", "")
            año     = (item.get("releaseDate") or item.get("firstAirDate") or "")[:4]
            estado  = item.get("mediaInfo", {}).get("status", 0)
            estados = {1: "✅ Available", 2: "⏳ Pending", 3: "⏳ Processing", 4: "⏳ Partial", 5: "✅ Available"}
            out.append(f"{titulo} ({año}) [{tipo}] — {estados.get(estado, '❌ Unavailable')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyseerr: {e}"


def jellyseerr_requests_pendientes():
    try:
        r = requests.get(f"{JELLYSEERR_URL}/api/v1/request",
            params={"filter": "pending", "take": 10},
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        items = r.json().get("results", [])
        if not items:
            return "There are no pending requests."
        out = []
        for item in items:
            media     = item.get("media", {})
            titulo    = media.get("originalTitle") or media.get("originalName") or "Unknown"
            solicitante = item.get("requestedBy", {}).get("displayName", "?")
            out.append(f"ID:{item['id']} — {titulo} (requested by {solicitante})")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyseerr: {e}"


def jellyseerr_aprobar(request_id):
    try:
        r = requests.post(f"{JELLYSEERR_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        return f"Request {request_id} approved." if r.status_code == 200 else f"Error: {r.status_code}"
    except Exception as e:
        return f"Error Jellyseerr: {e}"


# ── Radarr ───────────────────────────────────────────────────────────
def radarr_buscar(query):
    try:
        r = requests.get(f"{RADARR_URL}/api/v3/movie/lookup",
            params={"term": query},
            headers={"X-Api-Key": RADARR_KEY}, timeout=10)
        resultados = r.json()[:5]
        if not resultados:
            return "No movies found."
        out = []
        for m in resultados:
            estado = "✅ In library" if m.get("hasFile") else "❌ Not downloaded"
            out.append(f"{m['title']} ({m.get('year','?')}) — {estado}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Radarr: {e}"


def radarr_estado():
    try:
        r = requests.get(f"{RADARR_URL}/api/v3/movie",
            headers={"X-Api-Key": RADARR_KEY}, timeout=10)
        peliculas   = r.json()
        total       = len(peliculas)
        descargadas = sum(1 for p in peliculas if p.get("hasFile"))
        return f"Total: {total} | Downloaded: {descargadas} | Missing: {total - descargadas}"
    except Exception as e:
        return f"Error Radarr: {e}"


# ── Sonarr ───────────────────────────────────────────────────────────
def sonarr_buscar(query):
    try:
        r = requests.get(f"{SONARR_URL}/api/v3/series/lookup",
            params={"term": query},
            headers={"X-Api-Key": SONARR_KEY}, timeout=10)
        resultados = r.json()[:5]
        if not resultados:
            return "No series found."
        out = []
        for s in resultados:
            out.append(f"{s['title']} — {s.get('seasonCount',0)} seasons — {s.get('status','?')}")
        return "\n".join(out)
    except Exception as e:
        return f"Error Sonarr: {e}"


def sonarr_estado():
    try:
        r = requests.get(f"{SONARR_URL}/api/v3/series",
            headers={"X-Api-Key": SONARR_KEY}, timeout=10)
        return f"Total series: {len(r.json())}"
    except Exception as e:
        return f"Error Sonarr: {e}"
