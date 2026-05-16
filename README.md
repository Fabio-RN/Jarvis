# Jarvis

Asistente de servidor para NAS/Linux. Combina una API web, un bot de Discord y un loop LLM con tool-calling real sobre la infraestructura local.

**Versión actual: V3.5**

---

## Qué hace

- **Chat con herramientas reales**: el agente puede consultar el estado del sistema, reiniciar contenedores, buscar medios, controlar Home Assistant y ejecutar comandos, todo desde una conversación natural.
- **Dashboard web**: CPU, RAM, disco, temperatura, red (KB/s reales), contenedores y logs en tiempo real.
- **Consola web interactiva**: terminal estilo SSH directamente en el navegador, sin pasar por el LLM.
- **Bot de Discord**: mismo agente accesible desde canal o DM, con consola remota propia.
- **Vigilante**: monitoreo proactivo con alertas y auto-reinicio limitado de contenedores.
- **Reparador**: diagnóstico automático de errores, clasificación por patrones y remediación guiada.
- **Watchdog de hilos**: monitorea que Discord y los agentes sigan vivos; reinicia y notifica por DM si caen.

---

## Stack

- Python 3.12
- FastAPI + uvicorn
- discord.py
- openai SDK → OpenRouter (LLM principal)
- psutil, pydantic, requests, pyyaml, python-dotenv

---

## Estructura

```
jarvis/
├── main.py                  # Entrypoint
├── requirements.txt
├── web/
│   └── index.html           # Dashboard (sin framework)
├── api/
│   ├── server.py            # FastAPI + endpoints
│   ├── discord_bot.py       # Bot Discord
│   └── consola.py           # Consola interactiva Discord
├── agente/
│   ├── loop.py              # Orquestador LLM
│   ├── vigilante.py         # Monitoreo proactivo
│   └── reparador.py         # Diagnóstico y remediación
├── core/
│   ├── config.py            # Variables de entorno
│   ├── llm_client.py        # Cliente OpenRouter con fallback
│   ├── historial.py         # Historial multi-origen
│   ├── sistema.py           # Métricas y run_command
│   ├── actividad.py
│   └── tokens.py
├── tools/
│   ├── definiciones.py      # Esquema de tools para el LLM
│   ├── ejecutor.py          # Dispatcher
│   └── integraciones/
│       ├── media.py         # Radarr, Sonarr, Prowlarr, Jellyseerr
│       ├── descargas.py     # qBittorrent
│       ├── docker.py        # Docker / compose
│       ├── homeassistant.py
│       ├── jellyfin.py
│       ├── automatizacion.py # n8n, Filebrowser
│       └── sitios.py        # Descubrimiento de servicios
└── data/                    # JSON de runtime (no incluidos en repo)
```

---

## Instalación

```bash
git clone https://github.com/tu-user/jarvis.git
cd jarvis

pip install -r requirements.txt --break-system-packages

cp .env.example .env
# Editar .env con tus valores

python main.py
```

La API queda disponible en `http://<IP>:8888`.

---

## Configuración

Copia `.env.example` a `.env` y completa:

| Variable | Descripción |
|---|---|
| `IP` | IP local del servidor |
| `OPENROUTER_API_KEY` | Clave de OpenRouter (LLM) |
| `GROQ_API_KEY` | Clave de Groq (cliente auxiliar) |
| `DISCORD_TOKEN` | Token del bot de Discord |
| `DISCORD_CANAL_ID` | ID del canal donde responde el bot |
| `DISCORD_DM_ID` | ID del usuario owner (DMs + consola) |
| `RADARR_KEY` | API key de Radarr |
| `SONARR_KEY` | API key de Sonarr |
| `PROWLARR_KEY` | API key de Prowlarr |
| `JELLYFIN_KEY` | API key de Jellyfin |
| `JELLYSEERR_KEY` | API key de Jellyseerr |
| `QBIT_USER` / `QBIT_PASS` | Credenciales qBittorrent |
| `HA_TOKEN` | Token de Home Assistant |
| `N8N_USER` / `N8N_PASS` | Credenciales n8n |
| `FB_USER` / `FB_PASS` | Credenciales Filebrowser |
| `DATA_DIR` | Ruta de datos (ej: `/srv/nas/assistant/data`) |

Las integraciones de media, descargas y automatización son opcionales: si no configuras una clave, esa integración simplemente no funcionará.

---

## LLM

Proveedor: **OpenRouter** con fallback automático entre modelos:

1. `meta-llama/llama-3.3-70b-instruct:free`
2. `mistralai/devstral-small:free`
3. `nvidia/llama-3.1-nemotron-nano-8b-v1:free`
4. `openrouter/free`

El vigilante usa `nvidia/llama-3.1-nemotron-nano-8b-v1:free` como modelo auxiliar.

---

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/chat` | Chat con el agente |
| `POST` | `/cmd` | Ejecutar comando directo (consola web) |
| `GET` | `/stats` | CPU, RAM, disco, red, temperatura, contenedores |
| `GET` | `/health` | Estado del sistema (`ok / warn / critical`) |
| `GET` | `/logs/{contenedor}` | Últimas 100 líneas de logs Docker |
| `GET` | `/tokens` | Uso de tokens del día |
| `GET/POST` | `/vigilante` | Config del vigilante |
| `POST` | `/vigilante/toggle` | Activar/desactivar vigilante |
| `POST` | `/docker/restart/{nombre}` | Reiniciar contenedor |
| `POST` | `/docker/up` | `docker compose up -d` en todos los composes |
| `POST` | `/docker/down` | `docker compose down` en todos los composes |
| `POST` | `/sistema/reiniciar` | `sudo reboot` |
| `POST` | `/sistema/apagar` | `sudo poweroff` |
| `GET/POST/DELETE` | `/consola/permisos` | Gestión de usuarios de la consola Discord |

---

## Consola web

Accesible desde la pestaña **💻 Consola** del dashboard.

- Terminal estilo SSH con prompt `usuario@jarvis:/ruta$`
- Historial navegable con ↑↓ (hasta 100 entradas)
- `Ctrl+L` para limpiar
- Atajos rápidos: `ps`, `df`, `mem`, `temp`, `ports`, `net`, `uptime`, `docker ps`
- Confirmación modal para comandos destructivos (`rm`, `docker system prune`, `reboot`, etc.)
- Ejecuta contra `POST /cmd` directamente, sin pasar por el LLM

---

## Consola Discord

Disponible en DMs con el bot mediante `!console`.

```
!console           # Abrir sesión
!console /ruta     # Abrir sesión en ruta específica
!exit              # Cerrar sesión
!history           # Ver historial de sesión
!help              # Ayuda
```

Atajos: `!ps`, `!df`, `!mem`, `!temp`, `!ports`, `!whoami`, `!uptime`, `!net`, `!logs <contenedor>`, `!cat <archivo>`

Acceso restringido al owner por defecto. Usuarios adicionales se gestionan desde la web en **IA/Actividad → Permisos de consola**.

---

## Vigilante

Monitoreo proactivo configurable desde el dashboard o via API.

Valores por defecto:

```json
{
  "activo": true,
  "intervalo": 300,
  "cpu_umbral": 90,
  "ram_umbral": 85,
  "disco_umbral": 85,
  "temp_umbral": 80,
  "resumen_hora": 0
}
```

- Auto-reinicio de contenedores caídos: máximo 2 intentos, cooldown de 600s.
- Resumen diario enviado por DM con ventana de ±5 minutos.
- Las alertas críticas van siempre por DM, no al canal público.

---

## Reparador

Corre en background cada 120 segundos.

- Detecta contenedores detenidos y analiza sus logs.
- Clasifica errores: `config` (YAML inválido, puerto ocupado, permisos) o `transitorio` (OOM, connection refused, timeout).
- Los errores de configuración se reportan con fix sugerido sin reiniciar.
- Los errores transitorios se intentan reparar con reinicio y revalidación.
- No edita archivos de configuración por su cuenta.

---

## Integraciones soportadas

| Servicio | Puerto por defecto |
|---|---|
| Radarr | 7878 |
| Sonarr | 8989 |
| Prowlarr | 9696 |
| Jellyfin | 8096 |
| Jellyseerr | 5055 |
| qBittorrent | 8081 |
| Home Assistant | 8123 |
| n8n | 5678 |
| Filebrowser | 8080 |

---

## Notas de despliegue

- El proyecto asume Linux con Docker instalado y acceso a `journalctl`.
- Los compose se buscan bajo `/srv/nas/docker` por defecto (ajustable en `tools/integraciones/docker.py`).
- `docker_compose_up` y `docker_compose_down` son **globales**: afectan todos los composes del árbol.
- Para que `/health` detecte el estado de los hilos, `main.py` debe llamar `register_hilo(nombre, hilo)` importado de `api.server` tras iniciar cada hilo.
- El primer poll de `/stats` devuelve `sent_kbps: 0` y `recv_kbps: 0` hasta la segunda lectura (comportamiento esperado).

---

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md).

**V3.5** — Consola web interactiva, indicador de estado dinámico en header, `/health` con niveles diferenciados, fix de KB/s reales en `/stats`.

**V3.4** — Historial separado por origen (web/discord/dm), watchdog de hilos, permisos de consola Discord, panel de logs mejorado, reparador con diagnóstico específico.

**V3** — Rediseño completo: de chatbot reactivo a agente con tools reales. Arquitectura modular: `core/`, `tools/`, `agente/`, `api/`.

---

## Licencia

Uso personal. Con licencia abierta (MIT).
