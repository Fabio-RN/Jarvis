"""
Integration with web sites hosted on the server.

- Auto-detects services running on known ports
- Reads day counters from their JSON endpoint (port 8082)
- Exposes functions for the LLM and Discord
"""
import subprocess
import requests
import json
import os
from datetime import datetime, date

KNOWN_PORTS = {
    80:   "Nginx (HTTP)",
    443:  "Nginx (HTTPS)",
    8080: "Filebrowser",
    8081: "qBittorrent",
    8082: "Day Counter",
    8083: "Custom web",
    8084: "Custom web",
    8085: "Custom web",
    8086: "Custom web",
    8087: "Custom web",
    8088: "Custom web",
    8089: "Custom web",
    8096: "Jellyfin",
    8123: "Home Assistant",
    8888: "Jarvis",
    3000: "Grafana / Node app",
    3001: "Custom app",
    5000: "Flask/custom app",
    5678: "n8n",
    7878: "Radarr",
    8989: "Sonarr",
    9696: "Prowlarr",
    9000: "Portainer",
    9090: "Prometheus",
}

LOCAL_IP = "192.168.1.12"
COUNTER_URL  = f"http://{LOCAL_IP}:8082/contadores.json"
COUNTER_HTML = f"http://{LOCAL_IP}:8082"


def detect_active_ports() -> list[dict]:
    try:
        result = subprocess.run(
            "ss -tlnp | grep LISTEN | awk '{print $4}' | grep -oP ':\\K[0-9]+'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        ports = set()
        for line in result.stdout.strip().splitlines():
            try:
                ports.add(int(line.strip()))
            except:
                pass

        sites = []
        for port in sorted(ports):
            name = KNOWN_PORTS.get(port, "Unknown service")
            sites.append({
                "port":   port,
                "name":   name,
                "url":    f"http://{LOCAL_IP}:{port}",
                "known":  port in KNOWN_PORTS
            })
        return sites
    except Exception as e:
        return [{"error": str(e)}]


def get_sites_summary() -> str:
    sites = detect_active_ports()
    if not sites:
        return "No active web services detected."
    out = ["**Detected web services:**"]
    for s in sites:
        if "error" in s:
            out.append(f"Error: {s['error']}")
        else:
            out.append(f"  :{s['port']} — {s['name']} ({s['url']})")
    return "\n".join(out)


def list_sites_discord() -> str:
    sites = detect_active_ports()
    if not sites:
        return "No active web services detected."
    known   = [s for s in sites if s.get("known") and "error" not in s]
    unknown = [s for s in sites if not s.get("known") and "error" not in s]
    lines = ["**🌐 Web services on the server:**\n```"]
    for s in known:
        lines.append(f"  ✅ :{s['port']:5}  {s['name']}")
    if unknown:
        lines.append("")
        for s in unknown:
            lines.append(f"  ❓ :{s['port']:5}  {s['name']}")
    lines.append("```")
    return "\n".join(lines)


# ── Day counters ──────────────────────────────────────────────────────

def get_counters() -> list[dict]:
    try:
        r = requests.get(COUNTER_URL, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []


def _calculate_days(date_str: str, time_str: str = "00:00", include_weekends: bool = True) -> dict:
    try:
        from datetime import timedelta
        h, m = map(int, (time_str or "00:00").split(":"))
        year, month, day = map(int, date_str.split("-"))
        target  = datetime(year, month, day, h, m)
        now     = datetime.now()
        delta   = target - now
        days    = delta.days
        seconds = int(delta.total_seconds())

        if not include_weekends and days != 0:
            d    = now.date()
            end  = target.date()
            step = 1 if end > d else -1
            business_days = 0
            current = d
            while current != end:
                current += __import__('datetime').timedelta(days=step)
                if current.weekday() < 5:
                    business_days += step
            days = business_days

        return {
            "days":     abs(days),
            "past":     days < 0,
            "today":    days == 0,
            "seconds": abs(seconds),
            "hours":   abs(seconds) // 3600 % 24,
            "minutes": abs(seconds) // 60 % 60,
        }
    except Exception as e:
        return {"error": str(e)}


def get_counters_summary() -> str:
    counters = get_counters()
    if not counters:
        return (
            f"📅 **Day Counter**\n"
            f"Could not read counter at `{COUNTER_URL}`\n"
            f"Verify the server is running on port 8082."
        )

    lines = ["📅 **Day counters:**\n```"]
    for c in counters:
        name    = c.get("name", "?")
        emoji   = c.get("emoji", "📅")
        date    = c.get("date", "")
        time    = c.get("time", "00:00")
        weekends = c.get("includeWeekends", True)
        info    = _calculate_days(date, time, weekends)

        if "error" in info:
            lines.append(f"  {emoji} {name}: error calculating")
            continue

        if info["today"]:
            lines.append(f"  {emoji} {name}: TODAY 🎉")
        elif info["past"]:
            lines.append(f"  {emoji} {name}: {info['days']} days ago")
        else:
            lines.append(f"  {emoji} {name}: {info['days']} days remaining")

    lines.append(f"```\n🔗 {COUNTER_HTML}")
    return "\n".join(lines)


def get_day_counters_for_llm() -> str:
    counters = get_counters()
    if not counters:
        return f"Could not access day counter at {COUNTER_URL}."

    lines = ["Configured day counters:"]
    for c in counters:
        name    = c.get("name", "?")
        date    = c.get("date", "")
        time    = c.get("time", "00:00")
        weekends = c.get("includeWeekends", True)
        info    = _calculate_days(date, time, weekends)

        if "error" in info:
            lines.append(f"- {name}: error calculating ({date})")
            continue

        if info["today"]:
            lines.append(f"- {name} (date: {date}): TODAY")
        elif info["past"]:
            lines.append(f"- {name} (date: {date}): {info['days']} days ago")
        else:
            lines.append(
                f"- {name} (date: {date}): {info['days']} days remaining "
                f"({info['hours']}h {info['minutes']}m left)"
            )

    return "\n".join(lines)
