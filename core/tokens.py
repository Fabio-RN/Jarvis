"""
Contador de tokens persistente con historial por día.
- Guarda en data/tokens.json (estado del día actual)
- Guarda en data/tokens_historial.json (últimos 30 días)
- Separa tokens de web vs discord
- Al cambiar el día, archiva el día anterior automáticamente
"""
import json
import os
import threading
from datetime import datetime, date
from core.config import TOKENS_FILE

_lock          = threading.Lock()
HISTORIAL_FILE = TOKENS_FILE.replace("tokens.json", "tokens_historial.json")
MAX_DIAS       = 30  # máximo de días en el historial


def _cargar() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            try:
                return json.load(f)
            except:
                pass
    return _estado_inicial()


def _estado_inicial() -> dict:
    return {
        "fecha":       str(date.today()),
        "web":         0,
        "discord":     0,
        "total":       0,
        "limite":      200000,
        "modelo":      "openrouter/free",
        "ultima_sync": None,
    }


def _guardar(estado: dict):
    with _lock:
        with open(TOKENS_FILE, "w") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)


def _archivar_dia(estado: dict):
    """Guarda el estado del día en el historial antes de resetearlo."""
    if estado.get("total", 0) == 0:
        return  # no archivar días vacíos

    historial = _cargar_historial()

    entrada = {
        "fecha":   estado.get("fecha", str(date.today())),
        "web":     estado.get("web", 0),
        "discord": estado.get("discord", 0),
        "total":   estado.get("total", 0),
        "modelo":  estado.get("modelo", "openrouter/free"),
    }

    # Evitar duplicados del mismo día
    historial = [h for h in historial if h.get("fecha") != entrada["fecha"]]
    historial.insert(0, entrada)

    # Limitar tamaño
    historial = historial[:MAX_DIAS]

    with _lock:
        with open(HISTORIAL_FILE, "w") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)


def _cargar_historial() -> list:
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE) as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def agregar(tokens: int, origen: str = "web", modelo: str = None):
    estado = _cargar()

    # Si cambió el día → archivar el anterior y resetear
    if estado.get("fecha") != str(date.today()):
        _archivar_dia(estado)
        estado = _estado_inicial()

    if origen == "web":
        estado["web"]     = estado.get("web", 0) + tokens
    elif origen == "discord":
        estado["discord"] = estado.get("discord", 0) + tokens

    estado["total"]       = estado.get("web", 0) + estado.get("discord", 0)
    if modelo:
        estado["modelo"]  = modelo
    estado["ultima_sync"] = datetime.now().strftime("%H:%M:%S")
    _guardar(estado)


def obtener() -> dict:
    estado = _cargar()

    if estado.get("fecha") != str(date.today()):
        _archivar_dia(estado)
        estado = _estado_inicial()
        _guardar(estado)

    return {
        "used":        estado.get("total", 0),
        "web":         estado.get("web", 0),
        "discord":     estado.get("discord", 0),
        "total":       estado.get("limite", 200000),
        "modelo":      estado.get("modelo", "openrouter/free"),
        "fecha":       estado.get("fecha"),
        "ultima_sync": estado.get("ultima_sync"),
        "pct":         round((estado.get("total", 0) / estado.get("limite", 200000)) * 100, 1),
    }


def obtener_historial() -> list:
    """Devuelve historial de días anteriores + hoy al final."""
    historial = _cargar_historial()
    hoy       = obtener()

    # Incluir hoy si tiene actividad
    entrada_hoy = {
        "fecha":   hoy["fecha"],
        "web":     hoy["web"],
        "discord": hoy["discord"],
        "total":   hoy["used"],
        "modelo":  hoy["modelo"],
        "es_hoy":  True,
    }

    # Quitar hoy si ya estaba en historial (evitar duplicado)
    historial = [h for h in historial if h.get("fecha") != hoy["fecha"]]

    if hoy["used"] > 0:
        historial.insert(0, entrada_hoy)

    return historial


def resetear():
    estado = _estado_inicial()
    _guardar(estado)


def set_modelo(modelo: str):
    estado = _cargar()
    estado["modelo"] = modelo
    _guardar(estado)
