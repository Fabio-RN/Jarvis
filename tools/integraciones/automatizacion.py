import requests
from core.config import N8N_URL, N8N_USER, N8N_PASS, FB_URL, FB_USER, FB_PASS


def n8n_list_workflows():
    try:
        r = requests.get(f"{N8N_URL}/api/v1/workflows",
            auth=(N8N_USER, N8N_PASS), timeout=10)
        workflows = r.json().get("data", [])
        if not workflows:
            return "No workflows found."
        out = []
        for w in workflows:
            active = "✅" if w.get("active") else "⏸️"
            out.append(f"{active} ID:{w['id']} — {w['name']}")
        return "\n".join(out)
    except Exception as e:
        return f"Error n8n: {e}"


def n8n_execute_webhook(webhook_url):
    try:
        r = requests.post(webhook_url, timeout=10)
        return f"Webhook executed. Status: {r.status_code}"
    except Exception as e:
        return f"Error n8n: {e}"


def fb_list_files(path="/"):
    try:
        r = requests.post(f"{FB_URL}/api/login",
            json={"username": FB_USER, "password": FB_PASS}, timeout=10)
        token = r.text.strip('"')
        r2 = requests.get(f"{FB_URL}/api/resources{path}",
            headers={"X-Auth": token}, timeout=10)
        items = r2.json().get("items", [])
        if not items:
            return f"No files in {path}."
        out = []
        for item in items[:15]:
            kind = "📁" if item.get("isDir") else "📄"
            out.append(f"{kind} {item['name']} — {round(item.get('size',0)/1024/1024,1)}MB")
        return "\n".join(out)
    except Exception as e:
        return f"Error Filebrowser: {e}"
