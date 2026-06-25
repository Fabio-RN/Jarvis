# 🤖 Jarvis — Timeline de Versiones

---

# 📦 Versiones registradas

| Versión                        | Fecha subida        | Estado                                        |
| ------------------------------ | ------------------- | --------------------------------------------- |
| `Jarvis.zip`                   | 14/03/2026 01:06 AM | Primera versión pública/base                  |
| `JarvisV2.zip`                 | 19/04/2026 04:41 PM | Consola Discord + mejoras backend             |
| `JarvisV3.zip`                 | 19/04/2026 09:01 PM | Rediseño IA + arquitectura modular            |
| `JarvisV3.1.zip`               | 18/04/2026 12:36 AM | Rama experimental previa a V3                 |
| `JarvisV3.1.1.zip`             | 02/05/2026 12:23 AM | Refinamiento y fixes                          |
| `JarvisV3.1.1 Data Folder.zip` | 02/05/2026 12:39 AM | Datos persistentes/configuración              |
| `JarvisV3.2.zip`               | 06/05/2026 10:43 PM | Inteligencia avanzada/tools                   |
| `Jarvis V3.3.zip`              | 08/05/2026 10:08 PM | Plataforma DevOps/HomeLab consolidada         |
| `Jarvis V3.4.zip`              | 13/05/2026          | Permisos consola + logs mejorados + watchdog  |
| `Jarvis V3.5.zip`              | 16/05/2026          | Consola web + health real + fix red + watchdog fix |

---

# 🟢 Jarvis V1
📅 14 Marzo 2026

## Objetivo
Crear un asistente IA básico conectado al NAS/servidor Ubuntu.

---

## Características principales

### Backend
- Python + FastAPI + Discord.py + API Groq

### IA
- LLaMA 3.3 70B vía Groq
- Historial JSON básico

### Sistema
- Monitoreo: CPU, RAM, Disco, Red

### Docker
- Detección de contenedores
- Control básico

### Discord
```bash
!stats  !containers  !up  !down
```

---

# 🟡 Jarvis V2
📅 19 Abril 2026 — 04:41 PM

## Cambio principal
Conversión de Jarvis en consola remota administrable desde Discord.

## Nuevas funciones

### 🖥️ Consola remota
```bash
!console
!console docker ps
```

### UI Discord
- embeds, botones, modales, panel interactivo

### Quick Actions
- Docker PS, Logs Jarvis, Puertos, Disco, CPU/RAM

---

# 🔵 Jarvis V3
📅 19 Abril 2026 — 09:01 PM

## Cambio principal
Rediseño completo. De chatbot reactivo a agente inteligente con herramientas reales.

## Cambios grandes

### Arquitectura modular
```text
assistant/
├── core/
├── tools/
├── agente/
├── api/
└── web/
```

### Agentic Loop
- Múltiples tool calls, razonamiento multi-step

### Seguridad
- Migración a `.env`, eliminación de keys hardcodeadas

---

# 🟣 Jarvis V3.1
📅 18 Abril 2026 — 12:36 AM

Rama experimental/preparación para V3. Memoria persistente, tools encadenadas, contexto dinámico.

---

# 🟣 Jarvis V3.1.1
📅 02 Mayo 2026 — 12:23 AM

Refinamiento de V3. Fixes internos, reorganización, mejoras de estabilidad y persistencia.

---

# 🗂️ Jarvis V3.1.1 Data Folder
📅 02 Mayo 2026 — 12:39 AM

Datos persistentes del sistema: historial, configuraciones, cachés, archivos runtime.

---

# 🔴 Jarvis V3.2
📅 06 Mayo 2026 — 10:43 PM

## Cambio principal
Expansión fuerte de capacidades IA e integraciones.

## Integraciones añadidas
Jellyfin, Radarr, Sonarr, Prowlarr, qBittorrent, Filebrowser, Docker, Home Assistant, n8n

## Prompt dinámico
Inyección automática de estado sistema, contenedores, temperatura, alertas.

---

# 🟠 Jarvis V3.3
📅 08 Mayo 2026 — 10:08 PM

Plataforma DevOps/HomeLab IA consolidada.

| Área | Tecnología |
|---|---|
| IA | OpenRouter + LLaMA 3.3 70B |
| Backend | Python + FastAPI |
| Bot | Discord.py |
| Infraestructura | Docker |
| NAS | Ubuntu Server |
| Automatización | n8n |
| Media Stack | Jellyfin ecosystem |

---

# 🟡 Jarvis V3.4
📅 13 Mayo 2026

## 🔐 Sistema de permisos de consola Discord
- Usuarios adicionales autorizados (no solo el owner)
- `data/consola_permisos.json`
- Prompt diferenciado: `fabio@jarvis` / `guest@jarvis`
- `GET/POST/DELETE /consola/permisos`
- Panel de gestión en la web

## 📋 Panel de logs mejorado
- Input de servicio custom
- Botón limpiar sin recargar
- Auto-refresh configurable: 1s / 3s / 5s / 10s / 30s
- Select con estado visual ✅ / ❌

## 🛡️ Watchdog de hilos
- Monitorea `discord`, `vigilante` y `reparador` individualmente cada 60s
- Reinicia automáticamente (máx 2 intentos por hilo)
- DM en cada evento: caída, reinicio, fallo definitivo
- Hilos registrados en `api.server` vía `register_hilo()` para que `/health` los consulte sin importar `main`

## 🔧 Reparador con diagnóstico más específico
- Extrae línea exacta del error
- Fix sugerido por categoría (YAML, puerto, permisos, OOM, etc.)
- Valida sintaxis compose antes de reiniciar
- No edita archivos

## 🛡️ Fix resumen diario del vigilante
- Ventana ±5 minutos para no perderse la hora configurada

---

# 🟢 Jarvis V3.5
📅 16 Mayo 2026

## 💻 Consola web interactiva
- Nueva pestaña "💻 Consola" en el dashboard web
- Terminal estilo SSH: prompt `fabio@jarvis:/ruta/actual$`
- Historial navegable con ↑↓ (hasta 100 entradas)
- Ctrl+L para limpiar
- Tracking de `cwd` persistido en el cliente entre comandos
- Atajos rápidos: `ps`, `df`, `mem`, `temp`, `ports`, `net`, `uptime`, `docker ps`
- Confirmación modal para comandos peligrosos (rm, docker prune, etc.)
- Coloreo automático de errores en output
- Nuevo endpoint `POST /cmd` — sin pasar por el loop LLM

## ⚡ Indicador de estado dinámico
- El `● Online` del header refleja el estado real desde `GET /health`
- Niveles: Online / Advertencias / Crítico / Offline
- Tooltip descartable: ✕ por item individual o "Marcar todo leído"
- Items silenciados se des-silencian solos si el problema desaparece y vuelve
- **Fix:** las alertas del health ya no se duplican en el panel lateral cada 15s — el tooltip es la única fuente de estado persistente; el panel lateral es solo para eventos puntuales
- **Fix:** alertas de contenedores caídos se eliminan del panel cuando el contenedor vuelve a `running`

## 🏥 `/health` mejorado
- `nivel: ok | warn | critical` con listas separadas de `problemas` y `advertencias`
- Incluye recursos (cpu/ram/disco/temp), hilos y tareas del reparador
- Umbrales diferenciados: crítico solo para situaciones realmente graves (≥90%, discord caído, ≥5 contenedores caídos)
- Hilo `agentes` caído es `warn` (watchdog lo reinicia), no `critical`
- Usa `_hilos_registrados` en `api.server` — sin acoplamiento con `main`
- **Fix:** eliminado `/health` duplicado que `main.py` registraba encima del de `server.py` — el viejo solo devolvía hilos sin recursos ni nivel

## 🌐 Fix velocidades de red
- `/stats` devuelve KB/s reales (diferencia entre dos lecturas de `psutil.net_io_counters()`)
- Antes: KB acumulados desde boot del sistema (bug)
- Frontend formatea automáticamente: B/s / KB/s / MB/s

## 🔧 Fix watchdog y registro de hilos
- **Fix:** `main.py` tenía dos dicts desconectados — `_hilos_monitoreados` (watchdog) y `_hilos_registrados` (server.py) nunca se sincronizaban, por eso `/health` siempre mostraba `hilos: {}`
- `_crear_hilo()` unifica creación, arranque y registro en una sola operación
- El watchdog ahora monitorea `discord`, `vigilante` y `reparador` por separado (antes agrupados en un único hilo `agentes`)
- Al reiniciar un hilo caído, también se actualiza el registro de `server.py` automáticamente
- El watchdog no se registra a sí mismo en `/health` (no tiene sentido monitorearse)

---

# 📈 Evolución general del proyecto

| Etapa | Evolución |
|---|---|
| V1 | Chatbot servidor básico |
| V2 | Consola remota Discord |
| V3 | Arquitectura modular IA |
| V3.1 | Reestructuración |
| V3.1.1 | Estabilidad |
| V3.2 | Inteligencia avanzada + integraciones |
| V3.3 | Plataforma DevOps/HomeLab IA |
| V3.4 | Permisos multi-usuario + observabilidad |
| V3.5 | Consola web + health real + fix red |

---

# 🧠 Notas importantes

## Features descartadas/no implementadas

### Rama experimental voz
NO implementado finalmente:
- Whisper, Piper, bocina Bluetooth, Wyoming, asistente físico

Quedó únicamente como idea/prototipo conceptual en `asistente.py`.

## Deuda técnica conocida

- `asistente.py` contiene `GROQ_API_KEY` hardcodeada — pendiente de rotar
- Frontend monolítico (un único HTML muy grande)
- Bastante uso de `shell=True`
- No hay tests ni tipado estricto

---

# 🎯 Estado actual de Jarvis

```text
Agente modular para administración de infraestructura y automatización doméstica/lab
con control de acceso multi-usuario, consola web interactiva,
observabilidad en tiempo real con indicadores de estado dinámicos,
watchdog funcional con registro unificado de hilos
y dashboard web con terminal SSH integrada
```