"""
Jarvis entrypoint.
- Thread 1: Discord bot
- Thread 2: watchdog agent
- Thread 3: repair agent
- Thread 4: thread watchdog (daemon)
- Main thread: uvicorn on port 8888

Thread registry:
  All threads are registered in api.server via register_thread()
  so GET /health can query them regardless of main.
  The thread watchdog uses its own local dict _monitored_threads
  to restart them, but also updates server.py's registry
  every time it restarts a thread.
"""

import threading
import time
import uvicorn

from core.config import IP

_monitored_threads: dict[str, threading.Thread] = {}


def _start_discord():
    from api.discord_bot import run_bot
    run_bot()


def _start_watchdog():
    from agente.vigilante import start as start_watchdog
    from api.discord_bot import notify_dm, notify_channel
    start_watchdog(dm_fn=notify_dm, channel_fn=notify_channel)


def _start_repairer():
    from agente.reparador import start as start_repairer
    from api.discord_bot import notify_dm
    start_repairer(dm_fn=notify_dm)


def _create_thread(name: str, fn) -> threading.Thread:
    from api.server import register_thread
    t = threading.Thread(target=fn, name=name, daemon=True)
    t.start()
    register_thread(name, t)
    return t


def _restart_thread(name: str):
    factories = {
        "discord":   _start_discord,
        "watchdog":  _start_watchdog,
        "repairer":  _start_repairer,
    }
    fn = factories.get(name)
    if not fn:
        return None
    t = _create_thread(name, fn)
    _monitored_threads[name] = t
    return t


def _thread_watchdog():
    time.sleep(90)

    _retries: dict[str, int] = {}

    while True:
        try:
            from api.discord_bot import notify_dm

            for name, thread in list(_monitored_threads.items()):
                if thread.is_alive():
                    _retries.pop(name, None)
                    continue

                attempts = _retries.get(name, 0)

                if attempts == 0:
                    notify_dm(
                        f"⚠️ **Jarvis Watchdog** — "
                        f"thread `{name}` died. "
                        f"Attempting to restart..."
                    )

                if attempts < 2:
                    new_thread = _restart_thread(name)
                    if new_thread:
                        _retries[name] = attempts + 1
                        notify_dm(
                            f"🔧 **Jarvis Watchdog** — "
                            f"`{name}` restarted "
                            f"(attempt {attempts + 1}/2)"
                        )
                    else:
                        _retries[name] = 99
                        notify_dm(
                            f"🔴 **Jarvis Watchdog** — "
                            f"could not restart `{name}`."
                        )

                elif attempts < 99:
                    notify_dm(
                        f"🔴 **Jarvis Watchdog** — "
                        f"`{name}` still dead after 2 attempts. "
                        f"Manual intervention required."
                    )
                    _retries[name] = 99

        except Exception as e:
            print(f"[Thread Watchdog] Error: {e}")

        time.sleep(60)


if __name__ == "__main__":

    print("[Jarvis] Starting...")

    from api.server import app

    # ── Discord
    t_discord = _create_thread("discord", _start_discord)
    _monitored_threads["discord"] = t_discord
    print("[Jarvis] Discord thread started.")

    time.sleep(5)

    # ── Watchdog
    t_watchdog = _create_thread("watchdog", _start_watchdog)
    _monitored_threads["watchdog"] = t_watchdog
    print("[Jarvis] Watchdog thread started.")

    # ── Repairer
    t_repairer = _create_thread("repairer", _start_repairer)
    _monitored_threads["repairer"] = t_repairer
    print("[Jarvis] Repairer thread started.")

    # ── Thread watchdog
    t_thread_watchdog = threading.Thread(target=_thread_watchdog, name="thread-watchdog", daemon=True)
    t_thread_watchdog.start()
    print("[Jarvis] Thread watchdog started.")

    # ── FastAPI / uvicorn
    print(f"[Jarvis] API at http://{IP}:8888")
    uvicorn.run(app, host=IP, port=8888, log_level="warning")
