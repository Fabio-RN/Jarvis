import requests
from core.config import HA_URL, HA_TOKEN


def ha_entity_status():
    try:
        r = requests.get(f"{HA_URL}/api/states",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=10)
        entities = r.json()
        out = [f"{e['entity_id']}: {e['state']}" for e in entities[:20]]
        return "\n".join(out) if out else "No entities found."
    except Exception as e:
        return f"Error HA: {e}"


def ha_execute_service(domain, service, entity_id):
    try:
        r = requests.post(f"{HA_URL}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json={"entity_id": entity_id}, timeout=10)
        return f"Service {domain}.{service} executed on {entity_id}." if r.status_code == 200 else f"Error: {r.status_code}"
    except Exception as e:
        return f"Error HA: {e}"
