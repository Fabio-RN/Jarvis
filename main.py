"""
Entrypoint de Jarvis.
- Hilo 1: bot de Discord
- Hilo 2: vigilante
- Hilo 3: reparador
- Hilo 4: watchdog (daemon)
- Hilo principal: uvicorn en puerto 8888

Registro de hilos:
  Todos los hilos se registran en api.server via register_hilo()
  para que GET /health pueda consultarlos sin importar main.
  El watchdog usa su propio dict local _hilos_monitoreados para
  poder reiniciarlos, pero también actualiza el registro de server.py
  cada vez que reinicia un hilo.
"""

import threading
import time
import uvicorn

from core.config import IP

# ── Dict local del watchdog ───────────────────────────────────────────
# Separado de _hilos_registrados en server.py para evitar import circular.
# Se sincroniza con server.py via register_hilo() cada vez que se crea
# o reinicia un hilo.

_hilos_monitoreados: dict[str, threading.Thread] = {}


# ── Funciones de arranque de cada componente ──────────────────────────

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
    """Crea, arranca y registra un hilo en server.py."""
    from api.server import register_hilo
    t = threading.Thread(target=fn, name=nombre, daemon=True)
    t.start()
    register_hilo(nombre, t)
    return t


def _reiniciar_hilo(nombre: str):
    """Reinicia un hilo monitoreado y actualiza ambos registros."""
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
    Revisa cada 60s si los hilos siguen vivos.
    Si alguno cae, intenta reiniciarlo hasta 2 veces.
    Espera 90s al arranque para que Discord esté listo antes
    de intentar enviar DMs.
    """
    time.sleep(90)

    _reintentos: dict[str, int] = {}

    while True:
        try:
            from api.discord_bot import notificar_dm

            for nombre, hilo in list(_hilos_monitoreados.items()):
                if hilo.is_alive():
                    # Hilo vivo — resetear contador de reintentos
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
                    # Solo avisa una vez que superó los 2 intentos
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

    print("[Jarvis] Arrancando...")

    # Importar app primero para que register_hilo esté disponible
    from api.server import app

    # ── Discord
    t_discord = _crear_hilo("discord", _start_discord)
    _hilos_monitoreados["discord"] = t_discord
    print("[Jarvis] Hilo Discord arrancado.")

    # Esperar conexión inicial de Discord antes de arrancar el resto
    time.sleep(5)

    # ── Vigilante
    t_vigilante = _crear_hilo("vigilante", _start_vigilante)
    _hilos_monitoreados["vigilante"] = t_vigilante
    print("[Jarvis] Hilo Vigilante arrancado.")

    # ── Reparador
    t_reparador = _crear_hilo("reparador", _start_reparador)
    _hilos_monitoreados["reparador"] = t_reparador
    print("[Jarvis] Hilo Reparador arrancado.")

    # ── Watchdog
    t_watchdog = threading.Thread(target=_watchdog, name="watchdog", daemon=True)
    t_watchdog.start()
    # El watchdog no se registra en health ni se monitorea a sí mismo
    print("[Jarvis] Watchdog arrancado.")

    # ── FastAPI / uvicorn
    print(f"[Jarvis] API en http://{IP}:8888")
    uvicorn.run(app, host=IP, port=8888, log_level="warning")
