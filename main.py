"""
Jarvis entrypoint.
- Thread 1: Discord bot
- Thread 2: monitor
- Thread 3: repair
- Thread 4: watchdog daemon
- Main thread: uvicorn on port 8888

Thread registry:
  All threads are registered in api.server through register_thread()
  so GET /health can inspect them without depending on main.
  The watchdog uses its own local _monitored_threads dict so it can
  restart threads, but it also updates the registry in server.py
  every time it restarts one.
"""

import threading
import time
import uvicorn

from core.config import IP

# ── Local watchdog registry ───────────────────────────────────────────
# Separate from _registered_threads in server.py to avoid circular imports.
# It is synced with server.py through register_thread() whenever a thread
# is created or restarted.

_monitored_threads: dict[str, threading.Thread] = {}


# ── Startup functions for each component ──────────────────────────────

def _start_discord():
    from api.discord_bot import run_bot
    run_bot()


def _start_monitor():
    from agente.vigilante import start_monitor
    from api.discord_bot import notificar_dm, notificar_canal
    start_monitor(dm_sender=notificar_dm, channel_sender=notificar_canal)


def _start_repair():
    from agente.reparador import start_repair_agent
    from api.discord_bot import notificar_dm
    start_repair_agent(dm_sender=notificar_dm)


# ── Helpers ───────────────────────────────────────────────────────────

def _create_thread(name: str, target_fn) -> threading.Thread:
    """Create, start, and register a thread in server.py."""
    from api.server import register_thread
    thread = threading.Thread(target=target_fn, name=name, daemon=True)
    thread.start()
    register_thread(name, thread)
    return thread


def _restart_thread(name: str):
    """Restart a monitored thread and update both registries."""
    factories = {
        "discord":   _start_discord,
        "monitor": _start_monitor,
        "repair": _start_repair,
    }
    target_fn = factories.get(name)
    if not target_fn:
        return None
    thread = _create_thread(name, target_fn)
    _monitored_threads[name] = thread
    return thread


# ── Watchdog ──────────────────────────────────────────────────────────

def _watchdog():
    """
    Check every 60s whether the threads are still alive.
    If one dies, try to restart it up to 2 times.
    Wait 90s at startup so Discord is ready before
    trying to send DMs.
    """
    time.sleep(90)

    retry_counts: dict[str, int] = {}

    while True:
        try:
            from api.discord_bot import notificar_dm

            for name, thread in list(_monitored_threads.items()):
                if thread.is_alive():
                    # Thread is alive - reset retry counter
                    retry_counts.pop(name, None)
                    continue

                attempts = retry_counts.get(name, 0)

                if attempts == 0:
                    notificar_dm(
                        f"⚠️ **Jarvis Watchdog** — "
                        f"thread `{name}` crashed. "
                        f"Trying to restart it..."
                    )

                if attempts < 2:
                    restarted_thread = _restart_thread(name)
                    if restarted_thread:
                        retry_counts[name] = attempts + 1
                        notificar_dm(
                            f"🔧 **Jarvis Watchdog** — "
                            f"`{name}` restarted "
                            f"(attempt {attempts + 1}/2)"
                        )
                    else:
                        retry_counts[name] = 99
                        notificar_dm(
                            f"🔴 **Jarvis Watchdog** — "
                            f"could not restart `{name}`."
                        )

                elif attempts < 99:
                    # Notify only once after exceeding 2 attempts
                    notificar_dm(
                        f"🔴 **Jarvis Watchdog** — "
                        f"`{name}` is still down after 2 attempts. "
                        f"Manual intervention required."
                    )
                    retry_counts[name] = 99

        except Exception as e:
            print(f"[Watchdog] Error: {e}")

        time.sleep(60)


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("[Jarvis] Starting...")

    # Import the app first so register_hilo is available
    from api.server import app

    # ── Discord
    discord_thread = _create_thread("discord", _start_discord)
    _monitored_threads["discord"] = discord_thread
    print("[Jarvis] Discord thread started.")

    # Wait for Discord's initial connection before starting the rest
    time.sleep(5)

    # ── Monitor
    monitor_thread = _create_thread("monitor", _start_monitor)
    _monitored_threads["monitor"] = monitor_thread
    print("[Jarvis] Monitor thread started.")

    # ── Repair
    repair_thread = _create_thread("repair", _start_repair)
    _monitored_threads["repair"] = repair_thread
    print("[Jarvis] Repair thread started.")

    # ── Watchdog
    t_watchdog = threading.Thread(target=_watchdog, name="watchdog", daemon=True)
    t_watchdog.start()
    # The watchdog is not registered in health and does not monitor itself
    print("[Jarvis] Watchdog started.")

    # ── FastAPI / uvicorn
    print(f"[Jarvis] API at http://{IP}:8888")
    uvicorn.run(app, host=IP, port=8888, log_level="warning")
