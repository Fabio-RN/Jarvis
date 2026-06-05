"""
Historial de conversación con soporte de origen separado.
- web      → historial_web.json
- discord  → historial_discord.json
- dm       → historial_dm.json
- (vacío)  → historial.json  ← compatibilidad con código viejo
"""
import json
import os
from core.config import DATA_DIR

# Máximo de turnos que se persisten en disco por origen
MAX_TURNOS = 200

# Máximo de turnos recientes que se mandan al modelo
MAX_RECIENTE = 20

_ARCHIVOS = {
    "web":     os.path.join(DATA_DIR, "historial_web.json"),
    "discord": os.path.join(DATA_DIR, "historial_discord.json"),
    "dm":      os.path.join(DATA_DIR, "historial_dm.json"),
    "":        os.path.join(DATA_DIR, "historial.json"),   # legado
}


def _archivo(origen: str = "") -> str:
    return _ARCHIVOS.get(origen, _ARCHIVOS[""])


def cargar(origen: str = "") -> list:
    """Carga el historial del origen indicado desde disco."""
    path = _archivo(origen)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return []


def guardar(historial: list, origen: str = ""):
    """Persiste el historial en disco, truncando a MAX_TURNOS."""
    path = _archivo(origen)
    with open(path, "w") as f:
        json.dump(historial[-MAX_TURNOS:], f, ensure_ascii=False, indent=2)


def agregar(historial: list, rol: str, contenido: str, origen: str = "") -> list:
    """
    Agrega un turno al historial, lo persiste y devuelve la lista actualizada.
    rol: 'user' | 'assistant'
    """
    historial = historial + [{"role": rol, "content": contenido}]
    guardar(historial, origen)
    return historial


def reciente(historial: list) -> list:
    """Devuelve solo los últimos MAX_RECIENTE turnos para mandar al modelo."""
    return historial[-MAX_RECIENTE:]


def limpiar(origen: str = "") -> list:
    """Borra el historial del origen y devuelve lista vacía."""
    guardar([], origen)
    return []
