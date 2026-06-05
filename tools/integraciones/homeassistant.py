import requests
from core.config import HA_URL, HA_TOKEN


def ha_estado_entidades():
    try:
        r = requests.get(f"{HA_URL}/api/states",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=10)
        entidades = r.json()
        out = [f"{e['entity_id']}: {e['state']}" for e in entidades[:20]]
        return "\n".join(out) if out else "No entities found."
    except Exception as e:
        return f"Error HA: {e}"


def ha_ejecutar_servicio(dominio, servicio, entity_id):
    try:
        r = requests.post(f"{HA_URL}/api/services/{dominio}/{servicio}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json={"entity_id": entity_id}, timeout=10)
        return f"Service {dominio}.{servicio} executed on {entity_id}." if r.status_code == 200 else f"Error: {r.status_code}"
    except Exception as e:
        return f"Error HA: {e}"
