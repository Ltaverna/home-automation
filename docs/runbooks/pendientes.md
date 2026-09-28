# Pendientes

> Actualizado: 2026-09-28. Lo resuelto se mueve al final con fecha.

## Hardening pre-Fase 2 (del roadmap de arquitectura, ver `docs/roadmap-evolucion-arquitectura.md`)

Accionable sin la compra USA. Prioridad sugerida:
1. ~~Backup off-device cifrado~~ **HECHO 2026-09-28**: restic → Cloudflare R2 (`backup-offsite.sh`,
   cron 04:45 root, cifrado/incremental, retención 7d/4w/6m). Restore test OK. `RESTIC_PASSWORD`
   guardada fuera del R2130. Credenciales en `.restic-env` (fuera de git).
2. ~~Eliminar los webhooks~~ **HECHO 2026-09-28**: quitados de `packages/tv.yaml` (redundantes con
   HomeKit/MCP) y del entity registry. Sus IDs-credencial ya no están en git ni activos en HA.
3. ~~Observabilidad de nodo~~ **HECHO 2026-09-28**: `scripts/node-metrics.sh` (cron root cada 1 min)
   publica CPU/RAM/temp CPU/temp NVMe/disco/SMART del host a MQTT Discovery (device "Nodo R2130",
   entities `sensor.node_*` + `binary_sensor.node_nvme_smart`). Alerta `nodo_alerta` en
   `packages/salud.yaml` (disco>85%, temp CPU>80°C, SMART falla) y tarjeta en la vista "Salud".
   Liviano (sin Prometheus/Grafana). La temp del Hailo-8 no se expone (no hay hwmon/hailortcli
   on-demand) → se sustituye por la del NVMe. **✅ Hardening pre-Fase 2 COMPLETO (3/3).**

El resto del roadmap (Vision Fusion, Frigate person/dog, pose, dog classifier, CLIP, estado
semántico + MCP de dominio) es el norte, pero depende de la compra USA (sensores/cámara).

## Abiertos

- **Test de vida real de llegada/salida**: primera vez que Lucas salga del depto, verificar
  notificación AWAY (~5 min) + apagado de TVs, y HOME al volver. Ajustar geofence si es lento.
- **Configurar HACS** (está instalado, falta el login con GitHub en Settings → Integrations →
  Add → HACS). Sirve para updates automáticos de `samsungtv_smart`, `ha_mcp_tools` y futuras.
- **Fase 4**: verificar HailoRT del host == 4.21.0 (lo que exige Frigate 0.16); si no,
  script oficial `user_installation.sh` de Frigate, NO el paquete apt.
- **healthchecks.io**: crear el check gratuito y pegar la URL en `HEALTHCHECKS_URL` del `.env`
  de la R2130 (hoy vacío → el watchdog externo no pinguea todavía).

## Refactor de arquitectura (3 sub-proyectos)

- HECHO 2026-09-28: **Observabilidad** — `healthmon` (health-checks → MQTT), `binary_sensor.salud_*`,
  vista "Salud" en el dashboard, automatización `salud_alerta` (notif al caer/recuperar), y
  watchdog externo healthchecks.io (falta pegar la URL del check).
- PENDIENTE: **Parametrización** — mover valores casa-específicos (IPs, MACs, IDs Tizen,
  secret_path, grilla) a `secrets.yaml`; compose profiles; doc de onboarding de casa nueva.
- HECHO 2026-09-28: **Modularización** — config de HA reorganizada en `packages/` por feature
  (tv, house_mode, paseo, seguridad, face, salud). `automations.yaml`/`scripts.yaml` vacíos
  ([]/{}), se mantiene el !include. Verificado: mismo conjunto de entidades pre/post refactor.
  Fase 2 ahora suma un package (ej. `presencia.yaml`) en vez de engordar los monolitos.
- HECHO 2026-09-28: **Parametrización** — MACs (`lg_mac`/`samsung_mac`) y URL SmartThings (`st_url`)
  a `secrets.yaml` (+ `secrets.yaml.example`); compose profiles (`face`/`obs`) con `COMPOSE_PROFILES`
  en `.env`; doc `onboarding-casa-nueva.md`. entity_ids/IDs Tizen/grilla se cubren por convención +
  onboarding (HA no los parametriza). **✅ Refactor de arquitectura COMPLETO (los 3 sub-proyectos).**

## En progreso

- **MCP Server** (controlar la casa desde Claude/ChatGPT):
  - HECHO 2026-09-26: capa local — integración `mcp_server` activa (API assist), 13 entidades
    expuestas a Assist, endpoint `/mcp_server/sse` verificado (bearer token). Alcanzable por
    LAN/Tailscale.
  - HECHO 2026-09-26: exposición a internet resuelta con **HA-MCP** (`ha_mcp_tools` 8.5.0):
    - El `mcp_server` nativo NO sirve para ChatGPT (solo SSE legacy). Se migró a `ha_mcp_tools`
      (streamable HTTP + OAuth/DCR), compatible con ChatGPT y Claude.
    - Túnel Cloudflare dedicado `ha-mcp.neuralcore.dev` → `:9584` (contenedor `cloudflared-mcp`
      en docker-compose, credentials en `cloudflared/ha-mcp.json` fuera de git).
    - Connector: URL = `https://ha-mcp.neuralcore.dev` + secret_path (credencial, en la config
      entry / backup), auth "sin autenticación" (el secret_path es la credencial).
    - PENDIENTE: conectar y probar el connector en ChatGPT y Claude (el usuario).
    - Nota seguridad: el secret_path da acceso directo a la casa. Rotar con
      `regenerate_secrets` en el options flow si se filtra. Evaluar pasar a OAuth `ha_auth` puro
      más adelante si se quiere login en vez de secreto en URL.

## En progreso

- **Reconocimiento facial (experimental)**:
  - HECHO 2026-09-27: PoC funcionando. FaceEmbed API de Seeed dockerizada (`face-embed`,
    HailoRT 4.20 — NO hizo falta el upgrade a 4.21, los .hef cargan con 4.20). Cámara USB
    Redragon `/dev/video0`. Lucas enrolado (6 tomas, con y sin lentes); reconocimiento ~0.82
    de similaridad (threshold 0.45). Scripts `face-embed/scripts/{enroll,recognize}.py`.
  - PENDIENTE: decidir si se integra a HA (ej. reconocer en la entrada → evento MQTT →
    house_mode / notificación). Requiere pensar dónde/cuándo dispara (no correr inferencia
    24/7 sin motivo) y la privacidad. Reabre la decisión de la spec (que decía no face rec).
  - Nota: la cámara USB es de laboratorio; para producción en la entrada iría la cámara PoE
    de la compra USA (Fase 4) + Frigate para person/dog, y face rec solo en la zona de entrada.

## Proyectos futuros
- **Reporte diario** de ocupación/uso (resumen a las 23h). Baja prioridad.

## Decisiones registradas

- **Dominio neuralcore.dev (Cloudflare)**: NO exponer HA públicamente. Tailscale cubre el
  acceso remoto sin superficie de ataque. Reabrir solo si Tailscale molesta en el iPhone
  (conflicto con otro VPN) o hay que dar acceso a terceros → Cloudflare Tunnel + Access.
- **Apple TV: no comprar** (2026-09-19). No aporta nada al roadmap: acceso remoto ya resuelto
  (Tailscale), sin dispositivos Thread, la C3 ya tiene AirPlay 2, el remote del Centro de
  Control se logró vía HA, y la voz local viene con el Voice PE. Reevaluar solo como
  dispositivo de streaming/entretenimiento.
- **Apps del Samsung = cloud SmartThings**: única pieza cloud del sistema, sin alternativa
  local (Samsung capó el ws en 2020+). Aislada en `rest_command.st_tv_dormitorio_app`.

## Resueltos

- 2026-09-19 · Acceso remoto para geofence: **Tailscale** (descartado Nabu Casa por ahora).
- 2026-09-19 · LG C3 re-pareada limpia + Samsung Q60T integrada (luego migrada a
  `samsungtv_smart` con SmartThings; entidades `media_player.tv_dormitorio` + `remote.tv_dormitorio`).
- 2026-09-19 · Encendido remoto de ambas TVs validado por WoL (LG `38:06:E6:1C:26:70`,
  Samsung `68:72:C3:80:C4:A8`).
- 2026-09-19 · Apps en el dormitorio: resuelto vía HACS `ha-samsungtv-smart` + SmartThings API.
  IDs Tizen capturados empíricamente: Flow=`fCCrJTSe28.Flow`, Netflix=`org.tizen.netflix-app`,
  YouTube=`9Ur5IzDKqV.TizenYouTube`.
- 2026-09-19 · Sony HT-G700: sin red; controlada indirecto por HDMI-CEC a través del Samsung.
- 2026-09-28 · Reservadas las IPs en el router (`.14` LG, `.16` Samsung, `.17` R2130; MACs verificadas).
- 2026-09-28 · Quick Start+ activado en el LG: responde en standby, ya no se cae de la red.
- 2026-09-28 · Grilla Flow AMBA cargada en `flow_canal` (~55 canales + alias), corregida contra
  la TV real (LN+=15, A24=19; se ajusta sobre la marcha).
