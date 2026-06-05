"""
Integración con sitios web hosteados en el servidor.

- Detecta automáticamente servicios corriendo en puertos conocidos
- Lee el contador de días desde su endpoint JSON (puerto 8082)
- Expone funciones para el LLM y para Discord
"""
import subprocess
import requests
import json
import os
from datetime import datetime, date

# Puertos conocidos y sus nombres
PUERTOS_CONOCIDOS = {
    80:   "Nginx (HTTP)",
    443:  "Nginx (HTTPS)",
    8080: "Filebrowser",
    8081: "qBittorrent",
    8082: "Contador de días",
    8083: "Web custom",
    8084: "Web custom",
    8085: "Web custom",
    8086: "Web custom",
    8087: "Web custom",
    8088: "Web custom",
    8089: "Web custom",
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

IP_LOCAL = "192.168.1.12"
CONTADOR_URL = f"http://{IP_LOCAL}:8082/contadores.json"
CONTADOR_HTML = f"http://{IP_LOCAL}:8082"


def detectar_puertos_activos() -> list[dict]:
    """Escanea puertos activos en el servidor."""
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
            nombre = PUERTOS_CONOCIDOS.get(puerto, f"Servicio desconocido")
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
    """Resumen de sitios para el LLM."""
    sitios = detectar_puertos_activos()
    if not sitios:
        return "No se detectaron servicios web activos."
    out = ["**Servicios web detectados:**"]
    for s in sitios:
        if "error" in s:
            out.append(f"Error: {s['error']}")
        else:
            out.append(f"  :{s['puerto']} — {s['nombre']} ({s['url']})")
    return "\n".join(out)


def listar_sitios_discord() -> str:
    """Formato para Discord."""
    sitios = detectar_puertos_activos()
    if not sitios:
        return "No se detectaron servicios web activos."
    conocidos   = [s for s in sitios if s.get("conocido") and "error" not in s]
    desconocidos = [s for s in sitios if not s.get("conocido") and "error" not in s]
    lineas = ["**🌐 Servicios web en el servidor:**\n```"]
    for s in conocidos:
        lineas.append(f"  ✅ :{s['puerto']:5}  {s['nombre']}")
    if desconocidos:
        lineas.append("")
        for s in desconocidos:
            lineas.append(f"  ❓ :{s['puerto']:5}  {s['nombre']}")
    lineas.append("```")
    return "\n".join(lineas)


# ── Contador de días ──────────────────────────────────────────────────

def get_contadores() -> list[dict]:
    """
    Lee los contadores desde el endpoint JSON del contador.
    Si no existe el endpoint, devuelve lista vacía.
    """
    try:
        r = requests.get(CONTADOR_URL, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []


def _calcular_dias(fecha_str: str, tiempo_str: str = "00:00", incluir_finde: bool = True) -> dict:
    """Calcula días restantes/pasados desde una fecha."""
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
            # Contar solo días hábiles
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
    """Resumen de contadores para Discord."""
    contadores = get_contadores()
    if not contadores:
        return (
            f"📅 **Contador de días**\n"
            f"No se pudo leer el contador en `{CONTADOR_URL}`\n"
            f"Verificá que el servidor esté corriendo en el puerto 8082."
        )

    lineas = ["📅 **Contadores de días:**\n```"]
    for c in contadores:
        nombre = c.get("name", "?")
        emoji  = c.get("emoji", "📅")
        fecha  = c.get("date", "")
        tiempo = c.get("time", "00:00")
        finde  = c.get("includeWeekends", True)
        info   = _calcular_dias(fecha, tiempo, finde)

        if "error" in info:
            lineas.append(f"  {emoji} {nombre}: error calculando")
            continue

        if info["hoy"]:
            lineas.append(f"  {emoji} {nombre}: HOY 🎉")
        elif info["pasado"]:
            lineas.append(f"  {emoji} {nombre}: hace {info['dias']} días")
        else:
            lineas.append(f"  {emoji} {nombre}: {info['dias']} días restantes")

    lineas.append(f"```\n🔗 {CONTADOR_HTML}")
    return "\n".join(lineas)


def get_contadores_para_llm() -> str:
    """Formato detallado para el LLM."""
    contadores = get_contadores()
    if not contadores:
        return f"No se pudo acceder al contador de días en {CONTADOR_URL}."

    lineas = ["Contadores de días configurados:"]
    for c in contadores:
        nombre = c.get("name", "?")
        fecha  = c.get("date", "")
        tiempo = c.get("time", "00:00")
        finde  = c.get("includeWeekends", True)
        info   = _calcular_dias(fecha, tiempo, finde)

        if "error" in info:
            lineas.append(f"- {nombre}: error calculando ({fecha})")
            continue

        if info["hoy"]:
            lineas.append(f"- {nombre} (fecha: {fecha}): HOY")
        elif info["pasado"]:
            lineas.append(f"- {nombre} (fecha: {fecha}): hace {info['dias']} días")
        else:
            lineas.append(
                f"- {nombre} (fecha: {fecha}): faltan {info['dias']} días "
                f"({info['horas']}h {info['minutos']}m restantes)"
            )

    return "\n".join(lineas)
