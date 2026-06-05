"""
Integration with websites hosted on the server.

- Automatically detects services running on known ports
- Reads the day counter from its JSON endpoint (port 8082)
- Exposes functions for the LLM and for Discord
"""
import subprocess
import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, date

# Known ports and their names
PUERTOS_CONOCIDOS = {
    80:   "Nginx (HTTP)",
    443:  "Nginx (HTTPS)",
    8080: "Filebrowser",
    8081: "qBittorrent",
    8082: "Day Counter",
    8083: "Custom Web",
    8084: "Custom Web",
    8085: "Custom Web",
    8086: "Custom Web",
    8087: "Custom Web",
    8088: "Custom Web",
    8089: "Custom Web",
    8096: "Jellyfin",
    8123: "Home Assistant",
    8888: "Jarvis",
    3000: "Grafana / app Node",
    3001: "App custom",
    5000: "App Flask/custom",
    5678: "n8n",
    7878: "Radarr",
    8989: "Sonarr",
    9696: "Prowlarr",
    9000: "Portainer",
    9090: "Prometheus",
}

IP_LOCAL = os.getenv("IP_LOCAL", "{IP_LOCAL}")
CONTADOR_URL = f"http://{IP_LOCAL}:8082/contadores.json"
CONTADOR_HTML = f"http://{IP_LOCAL}:8082"


def detectar_puertos_activos() -> list[dict]:
    """Scan active ports on the server."""
    try:
        result = subprocess.run(
            "ss -tlnp | grep LISTEN | awk '{print $4}' | grep -oP ':\\K[0-9]+'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        puertos = set()
        for linea in result.stdout.strip().splitlines():
            try:
                puertos.add(int(linea.strip()))
            except:
                pass

        sitios = []
        for puerto in sorted(puertos):
            nombre = PUERTOS_CONOCIDOS.get(puerto, "Unknown service")
            sitios.append({
                "puerto": puerto,
                "nombre": nombre,
                "url": f"http://{IP_LOCAL}:{puerto}",
                "conocido": puerto in PUERTOS_CONOCIDOS
            })
        return sitios
    except Exception as e:
        return [{"error": str(e)}]


def get_sitios_resumen() -> str:
    """Site summary for the LLM."""
    sitios = detectar_puertos_activos()
    if not sitios:
        return "No active web services were detected."
    out = ["**Detected web services:**"]
    for s in sitios:
        if "error" in s:
            out.append(f"Error: {s['error']}")
        else:
            out.append(f"  :{s['puerto']} — {s['nombre']} ({s['url']})")
    return "\n".join(out)


def listar_sitios_discord() -> str:
    """Discord-friendly format."""
    sitios = detectar_puertos_activos()
    if not sitios:
        return "No active web services were detected."
    conocidos   = [s for s in sitios if s.get("conocido") and "error" not in s]
    desconocidos = [s for s in sitios if not s.get("conocido") and "error" not in s]
    lineas = ["**🌐 Web services on the server:**\n```"]
    for s in conocidos:
        lineas.append(f"  ✅ :{s['puerto']:5}  {s['nombre']}")
    if desconocidos:
        lineas.append("")
        for s in desconocidos:
            lineas.append(f"  ❓ :{s['puerto']:5}  {s['nombre']}")
    lineas.append("```")
    return "\n".join(lineas)


# ── Day counter ───────────────────────────────────────────────────────

def get_contadores() -> list[dict]:
    """
    Read counters from the counter JSON endpoint.
    If the endpoint does not exist, return an empty list.
    """
    try:
        r = requests.get(CONTADOR_URL, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []


def _calcular_dias(fecha_str: str, tiempo_str: str = "00:00", incluir_finde: bool = True) -> dict:
    """Calculate remaining/elapsed days from a date."""
    try:
        from datetime import timedelta
        h, m = map(int, (tiempo_str or "00:00").split(":"))
        año, mes, dia = map(int, fecha_str.split("-"))
        objetivo = datetime(año, mes, dia, h, m)
        ahora    = datetime.now()
        delta    = objetivo - ahora
        dias     = delta.days
        segundos = int(delta.total_seconds())

        if not incluir_finde and dias != 0:
            # Count only business days
            d    = ahora.date()
            fin  = objetivo.date()
            paso = 1 if fin > d else -1
            dias_habiles = 0
            actual = d
            while actual != fin:
                actual += __import__('datetime').timedelta(days=paso)
                if actual.weekday() < 5:
                    dias_habiles += paso
            dias = dias_habiles

        return {
            "dias":     abs(dias),
            "pasado":   dias < 0,
            "hoy":      dias == 0,
            "segundos": abs(segundos),
            "horas":    abs(segundos) // 3600 % 24,
            "minutos":  abs(segundos) // 60 % 60,
        }
    except Exception as e:
        return {"error": str(e)}


def get_contadores_resumen() -> str:
    """Counter summary for Discord."""
    contadores = get_contadores()
    if not contadores:
        return (
            f"📅 **Day Counter**\n"
            f"Could not read the counter at `{CONTADOR_URL}`\n"
            f"Check that the server is running on port 8082."
        )

    lineas = ["📅 **Day counters:**\n```"]
    for c in contadores:
        nombre = c.get("name", "?")
        emoji  = c.get("emoji", "📅")
        fecha  = c.get("date", "")
        tiempo = c.get("time", "00:00")
        finde  = c.get("includeWeekends", True)
        info   = _calcular_dias(fecha, tiempo, finde)

        if "error" in info:
            lineas.append(f"  {emoji} {nombre}: error calculating")
            continue

        if info["hoy"]:
            lineas.append(f"  {emoji} {nombre}: TODAY 🎉")
        elif info["pasado"]:
            lineas.append(f"  {emoji} {nombre}: {info['dias']} days ago")
        else:
            lineas.append(f"  {emoji} {nombre}: {info['dias']} days remaining")

    lineas.append(f"```\n🔗 {CONTADOR_HTML}")
    return "\n".join(lineas)


def get_contadores_para_llm() -> str:
    """Detailed format for the LLM."""
    contadores = get_contadores()
    if not contadores:
        return f"Could not access the day counter at {CONTADOR_URL}."

    lineas = ["Configured day counters:"]
    for c in contadores:
        nombre = c.get("name", "?")
        fecha  = c.get("date", "")
        tiempo = c.get("time", "00:00")
        finde  = c.get("includeWeekends", True)
        info   = _calcular_dias(fecha, tiempo, finde)

        if "error" in info:
            lineas.append(f"- {nombre}: error calculating ({fecha})")
            continue

        if info["hoy"]:
            lineas.append(f"- {nombre} (date: {fecha}): TODAY")
        elif info["pasado"]:
            lineas.append(f"- {nombre} (date: {fecha}): {info['dias']} days ago")
        else:
            lineas.append(
                f"- {nombre} (date: {fecha}): {info['dias']} days remaining "
                f"({info['horas']}h {info['minutos']}m left)"
            )

    return "\n".join(lineas)
