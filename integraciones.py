import requests
from config import *

def qbit_login():
    session = requests.Session()
    session.post(f"{QBIT_URL}/api/v2/auth/login", data={"username": QBIT_USER, "password": QBIT_PASS})
    return session

# ── Jellyseerr ──────────────────────────────────────────────────────
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
            tipo = item.get("mediaType", "")
            titulo = item.get("title") or item.get("name", "")
            año = (item.get("releaseDate") or item.get("firstAirDate") or "")[:4]
            estado = item.get("mediaInfo", {}).get("status", 0)
            estados = {1: "✅ Disponible", 2: "⏳ Pendiente", 3: "⏳ Procesando", 4: "⏳ Disponible parcial", 5: "✅ Disponible"}
            estado_txt = estados.get(estado, "❌ No disponible")
            out.append(f"{titulo} ({año}) [{tipo}] — {estado_txt}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

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
            media = item.get("media", {})
            titulo = media.get("originalTitle") or media.get("originalName") or "Desconocido"
            solicitante = item.get("requestedBy", {}).get("displayName", "?")
            out.append(f"ID:{item['id']} — {titulo} (pedido por {solicitante})")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def jellyseerr_aprobar(request_id):
    try:
        r = requests.post(f"{JELLYSEERR_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": JELLYSEERR_KEY}, timeout=10)
        if r.status_code == 200:
            return f"Request {request_id} aprobado."
        return f"Error al aprobar: {r.status_code}"
    except Exception as e:
        return f"Error: {e}"

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
            en_biblioteca = "✅ En biblioteca" if m.get("hasFile") else "❌ No descargada"
            out.append(f"{m['title']} ({m.get('year', '?')}) — {en_biblioteca}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def radarr_estado():
    try:
        r = requests.get(f"{RADARR_URL}/api/v3/movie",
            headers={"X-Api-Key": RADARR_KEY}, timeout=10)
        peliculas = r.json()
        total = len(peliculas)
        descargadas = sum(1 for p in peliculas if p.get("hasFile"))
        return f"Total películas: {total} | Descargadas: {descargadas} | Faltantes: {total - descargadas}"
    except Exception as e:
        return f"Error: {e}"

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
            estado = s.get("status", "?")
            temporadas = s.get("seasonCount", 0)
            out.append(f"{s['title']} — {temporadas} temporadas — Estado: {estado}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def sonarr_estado():
    try:
        r = requests.get(f"{SONARR_URL}/api/v3/series",
            headers={"X-Api-Key": SONARR_KEY}, timeout=10)
        series = r.json()
        total = len(series)
        return f"Total series: {total}"
    except Exception as e:
        return f"Error: {e}"

# ── qBittorrent ──────────────────────────────────────────────────────
def qbit_estado():
    try:
        session = qbit_login()
        r = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10)
        torrents = r.json()
        if not torrents:
            return "No hay torrents activos."
        out = []
        for t in torrents[:10]:
            estado = t.get("state", "?")
            progreso = round(t.get("progress", 0) * 100, 1)
            nombre = t.get("name", "?")[:40]
            out.append(f"{nombre} — {progreso}% — {estado}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def qbit_pausar(nombre):
    try:
        session = qbit_login()
        r = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10)
        torrents = r.json()
        for t in torrents:
            if nombre.lower() in t.get("name", "").lower():
                session.post(f"{QBIT_URL}/api/v2/torrents/pause", data={"hashes": t["hash"]})
                return f"Torrent '{t['name']}' pausado."
        return "No se encontró el torrent."
    except Exception as e:
        return f"Error: {e}"

def qbit_reanudar(nombre):
    try:
        session = qbit_login()
        r = session.get(f"{QBIT_URL}/api/v2/torrents/info", timeout=10)
        torrents = r.json()
        for t in torrents:
            if nombre.lower() in t.get("name", "").lower():
                session.post(f"{QBIT_URL}/api/v2/torrents/resume", data={"hashes": t["hash"]})
                return f"Torrent '{t['name']}' reanudado."
        return "No se encontró el torrent."
    except Exception as e:
        return f"Error: {e}"

# ── Jellyfin ─────────────────────────────────────────────────────────
def jellyfin_usuarios_conectados():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Sessions",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        sesiones = [s for s in r.json() if s.get("NowPlayingItem")]
        if not sesiones:
            return "No hay usuarios reproduciendo contenido ahora."
        out = []
        for s in sesiones:
            usuario = s.get("UserName", "?")
            item = s.get("NowPlayingItem", {}).get("Name", "?")
            out.append(f"{usuario} → reproduciendo: {item}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def jellyfin_estado_biblioteca():
    try:
        r = requests.get(f"{JELLYFIN_URL}/Items/Counts",
            headers={"X-Emby-Token": JELLYFIN_KEY}, timeout=10)
        d = r.json()
        return f"Películas: {d.get('MovieCount',0)} | Series: {d.get('SeriesCount',0)} | Episodios: {d.get('EpisodeCount',0)}"
    except Exception as e:
        return f"Error: {e}"
# ── Home Assistant ───────────────────────────────────────────────────
def ha_estado_entidades():
    try:
        r = requests.get(f"{HA_URL}/api/states",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=10)
        entidades = r.json()
        out = []
        for e in entidades[:20]:
            out.append(f"{e['entity_id']}: {e['state']}")
        return "\n".join(out) if out else "No hay entidades."
    except Exception as e:
        return f"Error: {e}"

def ha_ejecutar_servicio(dominio, servicio, entity_id):
    try:
        r = requests.post(f"{HA_URL}/api/services/{dominio}/{servicio}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json={"entity_id": entity_id}, timeout=10)
        if r.status_code == 200:
            return f"Servicio {dominio}.{servicio} ejecutado en {entity_id}."
        return f"Error: {r.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ── n8n ──────────────────────────────────────────────────────────────
def n8n_listar_workflows():
    try:
        r = requests.get(f"{N8N_URL}/api/v1/workflows",
            auth=(N8N_USER, N8N_PASS), timeout=10)
        workflows = r.json().get("data", [])
        if not workflows:
            return "No hay workflows."
        out = []
        for w in workflows:
            activo = "✅" if w.get("active") else "⏸️"
            out.append(f"{activo} ID:{w['id']} — {w['name']}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"

def n8n_ejecutar_webhook(webhook_url):
    try:
        r = requests.post(webhook_url, timeout=10)
        return f"Webhook ejecutado. Status: {r.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ── Filebrowser ──────────────────────────────────────────────────────
def fb_listar_archivos(ruta="/"):
    try:
        r = requests.post(f"{FB_URL}/api/login",
            json={"username": FB_USER, "password": FB_PASS}, timeout=10)
        token = r.text.strip('"')
        r2 = requests.get(f"{FB_URL}/api/resources{ruta}",
            headers={"X-Auth": token}, timeout=10)
        items = r2.json().get("items", [])
        if not items:
            return f"No hay archivos en {ruta}."
        out = []
        for item in items[:15]:
            tipo = "📁" if item.get("isDir") else "📄"
            out.append(f"{tipo} {item['name']} — {round(item.get('size',0)/1024/1024, 1)}MB")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"
