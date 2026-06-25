"""
Jarvis entrypoint.
- Thread 1: Discord bot
- Thread 2: watchdog agent
- Thread 3: repair agent
- Thread 4: thread watchdog (daemon)
- Main thread: uvicorn on port 8888

Thread registry:
  All threads are registered in api.server via register_hilo()
  so GET /health can query them regardless of main.
  The thread watchdog uses its own local dict _hilos_monitoreados
  to restart them, but also updates server.py's registry
  every time it restarts a thread.
"""

import threading
import time
import uvicorn

from core.config import IP

# ── Watchdog local dict ───────────────────────────────────────────
# Separated from _hilos_registrados in server.py to avoid circular import.
# Syncs with server.py via register_hilo() every time a thread is
# created or restarted.

_hilos_monitoreados: dict[str, threading.Thread] = {}


# ── Component startup functions ──────────────────────────────────

def _start_discord():
    from api.discord_bot import run_bot
    run_bot()


def _start_vigilante():
    from agente.vigilante import iniciar as iniciar_vigilante
    from api.discord_bot import notificar_dm, notificar_canal
    iniciar_vigilante(dm_fn=notificar_dm, canal_fn=notificar_canal)


def _start_reparador():
    from agente.reparador import iniciar as iniciar_reparador
    from api.discord_bot import notificar_dm
    iniciar_reparador(dm_fn=notificar_dm)


# ── Helpers ───────────────────────────────────────────────────────────

def _crear_hilo(nombre: str, fn) -> threading.Thread:
    """Creates, starts and registers a thread in server.py."""
    from api.server import register_hilo
    t = threading.Thread(target=fn, name=nombre, daemon=True)
    t.start()
    register_hilo(nombre, t)
    return t


def _reiniciar_hilo(nombre: str):
    """Restarts a monitored thread and updates both registries."""
    fabricas = {
        "discord":   _start_discord,
        "vigilante": _start_vigilante,
        "reparador": _start_reparador,
    }
    fn = fabricas.get(nombre)
    if not fn:
        return None
    t = _crear_hilo(nombre, fn)
    _hilos_monitoreados[nombre] = t
    return t


# ── Watchdog ──────────────────────────────────────────────────────────

def _watchdog():
    """
    Checks every 60s if threads are still alive.
    If one dies, tries to restart it up to 2 times.
    Waits 90s at startup so Discord is ready before
    attempting to send DMs.
    """
    time.sleep(90)

    _reintentos: dict[str, int] = {}

    while True:
        try:
            from api.discord_bot import notificar_dm

            for nombre, hilo in list(_hilos_monitoreados.items()):
                if hilo.is_alive():
                    # Thread alive — reset retry counter
                    _reintentos.pop(nombre, None)
                    continue

                intentos = _reintentos.get(nombre, 0)

                if intentos == 0:
                    notificar_dm(
                        f"⚠️ **Jarvis Watchdog** — "
                        f"el hilo `{nombre}` se cayó. "
                        f"Intentando reiniciar..."
                    )

                if intentos < 2:
                    nuevo = _reiniciar_hilo(nombre)
                    if nuevo:
                        _reintentos[nombre] = intentos + 1
                        notificar_dm(
                            f"🔧 **Jarvis Watchdog** — "
                            f"`{nombre}` reiniciado "
                            f"(intento {intentos + 1}/2)"
                        )
                    else:
                        _reintentos[nombre] = 99
                        notificar_dm(
                            f"🔴 **Jarvis Watchdog** — "
                            f"no pude reiniciar `{nombre}`."
                        )

                elif intentos < 99:
                    # Only warns once after exceeding 2 attempts
                    notificar_dm(
                        f"🔴 **Jarvis Watchdog** — "
                        f"`{nombre}` sigue caído tras 2 intentos. "
                        f"Intervención manual requerida."
                    )
                    _reintentos[nombre] = 99

        except Exception as e:
            print(f"[Watchdog] Error: {e}")

        time.sleep(60)


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("[Jarvis] Starting...")

    # Import app first so register_hilo is available
    from api.server import app

    # ── Discord
    t_discord = _crear_hilo("discord", _start_discord)
    _hilos_monitoreados["discord"] = t_discord
    print("[Jarvis] Discord thread started.")

    # Wait for initial Discord connection before starting the rest
    time.sleep(5)

    # ── Vigilante
    t_vigilante = _crear_hilo("vigilante", _start_vigilante)
    _hilos_monitoreados["vigilante"] = t_vigilante
    print("[Jarvis] Vigilante thread started.")

    # ── Reparador
    t_reparador = _crear_hilo("reparador", _start_reparador)
    _hilos_monitoreados["reparador"] = t_reparador
    print("[Jarvis] Reparador thread started.")

    # ── Watchdog
    t_watchdog = threading.Thread(target=_watchdog, name="watchdog", daemon=True)
    t_watchdog.start()
    # Watchdog is not registered in health and does not monitor itself
    print("[Jarvis] Watchdog started.")

    # ── FastAPI / uvicorn
    print(f"[Jarvis] API en http://{IP}:8888")
    uvicorn.run(app, host=IP, port=8888, log_level="warning")
