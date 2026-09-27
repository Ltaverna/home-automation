# 🏠 home-automation

Domótica local-first del depto de Lucas. Un solo nodo (Seeed **reComputer AI R2130**: Raspberry Pi 5 8GB + Hailo-8 26 TOPS + NVMe 512GB) corre todo el stack en Docker. Este repo es la fuente de verdad: compose, configs de Home Assistant y documentación.

## Filosofía

Local-first, simple, confiable, usable manualmente aunque HA falle. Regla por dispositivo:

```
API local → Zigbee/Matter → ESPHome → IR/RF → cloud (último recurso)
```

Spec completa: [`docs/superpowers/specs/2026-09-19-domotica-depto-design.md`](docs/superpowers/specs/2026-09-19-domotica-depto-design.md)

## Arquitectura

```
                    Router / WiFi
                         │
        ┌────────────────┼─────────────────────────┐
        │                │                         │
  reComputer R2130   LG OLED C3 (living)     Samsung Q60T (dorm.)
  192.168.1.17       192.168.1.14 · webOS    192.168.1.16 · Tizen
  Pi OS + Docker     WoL 38:06:E6:1C:26:70   WoL 68:72:C3:80:C4:A8
        │                │ óptico                  │
        │                ▼                   Sony HT-G700
        │          NAD D3020 V2              (sin red; vía HDMI-CEC)
        │          + Dynaudio Emit M10
        │          (volumen real acá; IR en Fase 3)
        ├── homeassistant (host network, :8123)
        ├── mosquitto (:1883, auth obligatoria)
        ├── face-embed (:8000, Hailo) · face-recognizer (loop→MQTT, pausado)
        ├── healthmon (salud→MQTT + dead-man) · cloudflared-mcp (túnel MCP)
        └── [Fase 2+] zigbee2mqtt · frigate+Hailo · esphome · music-assistant

  Acceso remoto: Tailscale → https://r2130.tail71f19f.ts.net (tailscale serve → :8123)
  Apple Home:    HomeKit Bridge (:21063) + TV Sala accessory (:21064) → Siri / remote iOS
  MCP (nube):    ha-mcp.neuralcore.dev (Cloudflare Tunnel → ha_mcp_tools :9584) → Claude/ChatGPT
```

## Servicios (docker-compose.yml)

Perfiles Docker (`COMPOSE_PROFILES` en `.env`): **base** siempre; `face` y `obs` opcionales.

| Servicio | Profile | Rol |
|---|---|---|
| `homeassistant` | base | Cerebro: automatizaciones, house modes, integraciones (host network, caps BT, dbus) |
| `mosquitto` | base | Broker MQTT (anónimo rechazado; passwd fuera de git) |
| `cloudflared-mcp` | base | Túnel Cloudflare dedicado → endpoint MCP (`ha_mcp_tools`) para Claude/ChatGPT |
| `face-embed` | face | Reconocimiento facial en Hailo-8 (SCRFD+ArcFace, API :8000) — HailoRT 4.20 |
| `face-recognizer` | face | Loop cámara→face-embed→MQTT (`sensor.ultima_cara`). **Pausado por defecto** |
| `healthmon` | obs | Health-checks HTTP→MQTT (`binary_sensor.salud_*`) + dead-man switch externo |

Dentro de HA además: **HACS** (instalado, pendiente de configurar) y las integraciones custom
**`samsungtv_smart`** (ollo69) y **`ha_mcp_tools`** (MCP server) en `custom_components/` (fuera de git).

Los secretos viven en `.env`, `mosquitto/config/passwd`, `homeassistant/secrets.yaml`
(`st_bearer`/`st_url`/`lg_mac`/`samsung_mac`) y `.restic-env` (credenciales R2) — todos fuera de git,
incluidos en los backups.

## Estructura del repo

```
├── docker-compose.yml
├── .env.example              → copiar a .env en la R2130
├── homeassistant/
│   ├── configuration.yaml    → core: default_config, http, homeassistant+packages, homekit, lovelace
│   ├── packages/             → config por feature (merge automático): tv, house_mode, paseo, seguridad, face, salud
│   │                           cada archivo agrupa sus automations + scripts + helpers
│   ├── automations.yaml / scripts.yaml → vacíos ([]/{}); todo migró a packages, se mantiene el !include
│   │                           (control TV por Siri/HomeKit + MCP; los webhooks de atajos se eliminaron)
│   ├── scenes.yaml
│   ├── dashboards/remoto.yaml → dashboard "Control remoto" (d-pad, dígitos, apps, 2 TVs, Salud)
│   ├── secrets.yaml          → st_bearer, st_url, lg_mac, samsung_mac (NO va a git; ver secrets.yaml.example)
│   └── custom_components/    → HACS + samsungtv_smart + ha_mcp_tools (NO va a git; en backup)
├── healthmon/ face-embed/ face-recognizer/ cloudflared/  → contenedores propios (Dockerfile)
├── mosquitto/config/mosquitto.conf
├── .restic-env(.example)     → credenciales R2 para el backup off-site (real fuera de git)
├── scripts/
│   ├── backup.sh             → cron 04:30 → /opt/backups (tar local, 14 días)
│   └── backup-offsite.sh     → cron 04:45 → Cloudflare R2 (restic cifrado, 7d/4w/6m)
└── docs/
    ├── estado-actual.md      → INVENTARIO VIVO: qué hay hoy y cómo se usa
    ├── roadmap-evolucion-arquitectura.md → norte del proyecto (semantic home / edge AI)
    ├── runbooks/
    │   ├── instalacion-r2130.md      → accesos, recovery (local + R2), gotchas
    │   ├── onboarding-casa-nueva.md  → instalar en otra casa (segunda instancia)
    │   └── pendientes.md             → decisiones, deuda, hardening
    └── superpowers/
        ├── specs/            → diseño aprobado (spec)
        └── plans/            → planes de implementación por fase
```

## Operación diaria

El workflow es **editar acá (mini-PC) → commit → push → pull en la R2130 → aplicar**:

```bash
# 1. editar archivos en este repo, commitear y pushear
git add -A && git commit -m "..." && git push

# 2. aplicar en la R2130
ssh r2130 'git -C /opt/home-automation pull'

# 3. recargar según qué se tocó (token en ~/.ha_token del mini-PC):
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
curl -X POST -H "$H" $BASE/services/automation/reload   # automations.yaml
curl -X POST -H "$H" $BASE/services/script/reload       # scripts.yaml
curl -X POST -H "$H" $BASE/services/template/reload     # template switches
# configuration.yaml / packages/ nuevos (helpers, homekit) → restart:
ssh r2130 'docker restart homeassistant'
```

**Perfiles de servicios:** `COMPOSE_PROFILES` en `.env` decide qué levanta cada casa
(`face` = face-embed + face-recognizer, requieren Hailo/cámara · `obs` = healthmon). La base
(mosquitto, homeassistant, cloudflared-mcp) siempre. Casa principal: `face,obs`.

**Instalar en otra casa:** ver [`docs/runbooks/onboarding-casa-nueva.md`](docs/runbooks/onboarding-casa-nueva.md).
El repo aporta la lógica (packages, scripts, compose); cada casa su contexto (`.env`, `secrets.yaml`,
`.storage`, túnel Cloudflare).

La R2130 tiene deploy key **read-only**: nunca commitea, solo pullea.

## Gotchas conocidos (leer antes de pelearse con HA)

1. **`http:` en YAML se ignora después del primer boot** — HA 2026 migra esa config a `.storage/http` (`yaml_migration_done: true`). Si cambiás `trusted_proxies` y no aplica: parar HA, borrar `.storage/http` (con backup), arrancar. Detalle en el runbook.
2. **Samsung 2020+: las apps solo se lanzan por la nube de SmartThings** — Samsung capó tanto el endpoint REST como el launch por websocket local. Resuelto con `rest_command.st_tv_dormitorio_app` (token en `secrets.yaml`); es la única pieza cloud del sistema. Teclas/power/dígitos/volumen siguen locales vía `remote.send_command KEY_*`.
3. **El picker de Atajos de iOS (App Intents) solo lista ciertos dominios** — scripts no aparecen; por eso los switches template. Su caché tarda en refrescar (reabrir app HA / reiniciar iPhone).
4. **Entidades fantasma del LG**: si la integración webostv se re-parea, HA puede resucitar entidades viejas con sufijo `_2`. Limpiar por WebSocket API (`config/entity_registry/remove` + `update`), no editando `.storage` a mano.
5. **samsungtv_smart tras un restart de HA** puede quedar con la conexión ws a medias (estado `off`/app `None` con la TV prendida, comandos que no llegan): recargar la config entry (Settings → Integrations → TV Dormitorio → Reload, o por API).
6. **El volumen del LG en HA no mueve el audio del living** — la salida óptica es de nivel fijo; el volumen real lo tiene el NAD (IR en Fase 3).
7. **El backup off-site corre como root** — `.storage`/`passwd` son de root; el cron es de root. Si se corre a mano, `sudo`. La `RESTIC_PASSWORD` vive fuera del R2130: sin ella el backup es irrecuperable.

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 1 — Base | R2130 + Docker + HA + MQTT + TVs + iPhone + Tailscale + backups | ✅ 2026-09-19 |
| 1.5 — Extras | house_mode, WoL, apps/canales en ambas TVs (LG local, Samsung vía ST), switches+Siri (HomeKit), remote Centro de Control iOS, dashboard control remoto, HACS | ✅ 2026-09-19 |
| MCP | `ha_mcp_tools` + Cloudflare Tunnel → controlar la casa desde Claude/ChatGPT | ✅ 2026-09-26 |
| Face rec (PoC) | FaceEmbed en Hailo (SCRFD+ArcFace) → `sensor.ultima_cara` + señal blanda | ✅ 2026-09-27 |
| Arquitectura | Observabilidad (healthmon) + modularización (packages) + parametrización (secrets/profiles/onboarding) | ✅ 2026-09-28 |
| Hardening | Backup off-site cifrado (restic→R2) ✅ · webhooks eliminados ✅ · observabilidad de nodo ⏳ | 🔶 en curso |
| 2 — Presencia | SLZB-06M + Zigbee2MQTT, sensor puerta, mmWave, llegada/salida reales | ⏳ espera compra USA |
| 3 — Living | Shelly Dimmer (electricista), ESP32 IR → NAD + aire, Modo Cine | ⏳ |
| 4 — Cámara + AI | HailoRT 4.21 + Frigate + Reolink, person/dog, modo CLEANING, face event-driven | ⏳ |
| 5 — Voz + audio | Voice PE, Music Assistant → USB-S/PDIF → NAD | ⏳ |

BOM de compra USA (verificado sept-2026, ~USD 505-545): ver la spec, sección BOM.
Norte del proyecto (semantic home / vision fusion / MCP de dominio): ver `docs/roadmap-evolucion-arquitectura.md`.
