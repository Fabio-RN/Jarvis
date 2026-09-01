import subprocess
import os


def _compose_dirs(base="/srv/nas/docker"):
    dirs = []
    for root, _, files in os.walk(base):
        if "docker-compose.yml" in files or "compose.yml" in files:
            dirs.append(root)
    return dirs


def docker_restart(name):
    try:
        result = subprocess.run(
            f"docker restart {name}",
            shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return f"✅ Container '{name}' restarted successfully."
        return f"❌ Error restarting '{name}': {result.stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"


def docker_compose_up():
    try:
        dirs = _compose_dirs()
        if not dirs:
            return "No docker-compose directories found."
        results = []
        for d in dirs:
            r = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=d, capture_output=True, text=True, timeout=60
            )
            name = os.path.basename(d)
            results.append(f"{'✅' if r.returncode == 0 else '❌'} {name}")
        return "docker compose up:\n" + "\n".join(results)
    except Exception as e:
        return f"Error: {e}"


def docker_compose_down():
    try:
        dirs = _compose_dirs()
        if not dirs:
            return "No docker-compose directories found."
        results = []
        for d in dirs:
            r = subprocess.run(
                ["docker", "compose", "down"],
                cwd=d, capture_output=True, text=True, timeout=60
            )
            name = os.path.basename(d)
            results.append(f"{'✅' if r.returncode == 0 else '❌'} {name}")
        return "docker compose down:\n" + "\n".join(results)
    except Exception as e:
        return f"Error: {e}"
