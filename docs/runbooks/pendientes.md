# Pendientes

> Actualizado: 2026-09-19 (noche). Lo resuelto se mueve al final con fecha.

## Abiertos

- **Reservar IPs en el DHCP del router**: 192.168.1.17 (R2130), 192.168.1.14 (LG),
  192.168.1.16 (Samsung).
- **Cargar la grilla Flow** nombre→número en `script.flow_canal` (Lucas la dicta desde la
  guía; hoy solo tiene `telefe: 10`).
- **Activar Quick Start+ en el LG**: hoy al apagarse queda `unavailable` (deep-off). El WoL
  la enciende igual, pero con Quick Start+ quedaría visible en standby y el estado sería
  más prolijo.
- **Test de vida real de llegada/salida**: primera vez que Lucas salga del depto, verificar
  notificación AWAY (~5 min) + apagado de TVs, y HOME al volver. Ajustar geofence si es lento.
- **Configurar HACS** (está instalado, falta el login con GitHub en Settings → Integrations →
  Add → HACS). Sirve para updates automáticos de `samsungtv_smart` y futuras integraciones.
- **Fase 4**: verificar HailoRT del host == 4.21.0 (lo que exige Frigate 0.16); si no,
  script oficial `user_installation.sh` de Frigate, NO el paquete apt.

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
