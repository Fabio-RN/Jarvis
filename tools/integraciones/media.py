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
            return "No se encontraron resultados."
        out = []
        for item in resultados:
            tipo    = item.get("mediaType", "")
            titulo  = item.get("title") or item.get("name", "")
            año     = (item.get("releaseDate") or item.get("firstAirDate") or "")[:4]
            estado  = item.get("mediaInfo", {}).get("status", 0)
            estados = {1: "✅ Disponible", 2: "⏳ Pendiente", 3: "⏳ Procesando", 4: "⏳ Parcial", 5: "✅ Disponible"}
            out.append(f"{titulo} ({año}) [{tipo}] — {estados.get(estado, '❌ No disponible')}")
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
            return "No hay requests pendientes."
        out = []
        for item in items:
            media     = item.get("media", {})
            titulo    = media.get("originalTitle") or media.get("originalName") or "Desconocido"
            solicitante = item.get("requestedBy", {}).get("displayName", "?")
            out.append(f"ID:{item['id']} — {titulo} (pedido por {solicitante})")
        return "\n".join(out)
    except Exception as e:
        return f"Error Jellyseerr: {e}"


def jellyseerr_aprobar(request_id):
    try:
        r = requests.post(f"{JELLYSEERR_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        return f"Request {request_id} aprobado." if r.status_code == 200 else f"Error: {r.status_code}"
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
            return "No se encontraron películas."
        out = []
        for m in resultados:
            estado = "✅ En biblioteca" if m.get("hasFile") else "❌ No descargada"
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
        return f"Total: {total} | Descargadas: {descargadas} | Faltantes: {total - descargadas}"
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
            return "No se encontraron series."
        out = []
        for s in resultados:
            out.append(f"{s['title']} — {s.get('seasonCount',0)} temporadas — {s.get('status','?')}")
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