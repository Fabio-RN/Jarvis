import json
import os
from datetime import datetime
from core.config import ACTIVIDAD_LOG


def registrar(tipo: str, texto: str, badge: str = ""):
    """
    tipo: 'tool' | 'alert' | 'ok' | 'warn' | 'cmd' | 'auto'
    """
    entrada = {
        "tipo": tipo,
        "texto": texto,
        "badge": badge,
        "hora": datetime.now().strftime("%H:%M:%S"),
        "fecha": datetime.now().strftime("%d/%m/%Y")
    }
    logs = cargar()
    logs.insert(0, entrada)
    with open(ACTIVIDAD_LOG, "w") as f:
        json.dump(logs[:200], f, ensure_ascii=False)


def cargar():
    if os.path.exists(ACTIVIDAD_LOG):
        with open(ACTIVIDAD_LOG) as f:
            try:
                return json.load(f)
            except:
                return []
    return []