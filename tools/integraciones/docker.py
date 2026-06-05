import subprocess
import os


def _compose_dirs(base="/srv/nas/docker"):
    dirs = []
    for root, _, files in os.walk(base):
        if "docker-compose.yml" in files or "compose.yml" in files:
            dirs.append(root)
    return dirs


def docker_restart(nombre):
    try:
        result = subprocess.run(
            f"docker restart {nombre}",
            shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return f"✅ Contenedor '{nombre}' reiniciado correctamente."
        return f"❌ Error reiniciando '{nombre}': {result.stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"


def docker_compose_up():
    try:
        dirs = _compose_dirs()
        if not dirs:
            return "No se encontraron directorios con docker-compose."
        resultados = []
        for d in dirs:
            r = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=d, capture_output=True, text=True, timeout=60
            )
            nombre = os.path.basename(d)
            resultados.append(f"{'✅' if r.returncode == 0 else '❌'} {nombre}")
        return "docker compose up:\n" + "\n".join(resultados)
    except Exception as e:
        return f"Error: {e}"


def docker_compose_down():
    try:
        dirs = _compose_dirs()
        if not dirs:
            return "No se encontraron directorios con docker-compose."
        resultados = []
        for d in dirs:
            r = subprocess.run(
                ["docker", "compose", "down"],
                cwd=d, capture_output=True, text=True, timeout=60
            )
            nombre = os.path.basename(d)
            resultados.append(f"{'✅' if r.returncode == 0 else '❌'} {nombre}")
        return "docker compose down:\n" + "\n".join(resultados)
    except Exception as e:
        return f"Error: {e}"