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
        │                                          │
        │                                    Sony HT-G700
        │                                    (sin red; vía HDMI-CEC)
        ├── homeassistant (host network, :8123)
        ├── mosquitto (:1883, auth obligatoria)
        └── [Fase 2+] zigbee2mqtt · frigate+Hailo · esphome · music-assistant

  Acceso remoto: Tailscale → https://r2130.tail71f19f.ts.net (tailscale serve → :8123)
  Apple Home:    HomeKit Bridge (:21063) → Siri nativo para los switches de apps
```

## Servicios (docker-compose.yml)

| Servicio | Rol | Notas |
|---|---|---|
| `homeassistant` | Cerebro: automatizaciones, house modes, integraciones | host network, caps BT (NET_ADMIN/NET_RAW), dbus |
| `mosquitto` | Broker MQTT | anónimo rechazado; passwd fuera de git |

Los secretos viven en `.env` y `mosquitto/config/passwd` (ambos fuera de git, incluidos en el backup nocturno).

## Estructura del repo

```
├── docker-compose.yml
├── .env.example              → copiar a .env en la R2130
├── homeassistant/
│   ├── configuration.yaml    → base + http/proxy + input_select + template switches + homekit
│   ├── automations.yaml      → house modes, WoL hook del LG, webhooks iOS
│   ├── scripts.yaml          → encendido TVs, apps, canales Flow
│   └── scenes.yaml
├── mosquitto/config/mosquitto.conf
├── scripts/backup.sh         → cron 04:30 en la R2130 → /opt/backups (retiene 14)
└── docs/
    ├── estado-actual.md      → INVENTARIO VIVO: qué hay hoy y cómo se usa
    ├── runbooks/
    │   ├── instalacion-r2130.md  → accesos, recovery desde cero, gotchas
    │   └── pendientes.md         → decisiones tomadas y deuda pendiente
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
# configuration.yaml (http, homekit, input_select nuevos) → restart:
ssh r2130 'docker restart homeassistant'
```

La R2130 tiene deploy key **read-only**: nunca commitea, solo pullea.

## Gotchas conocidos (leer antes de pelearse con HA)

1. **`http:` en YAML se ignora después del primer boot** — HA 2026 migra esa config a `.storage/http` (`yaml_migration_done: true`). Si cambiás `trusted_proxies` y no aplica: parar HA, borrar `.storage/http` (con backup), arrancar. Detalle en el runbook.
2. **Samsung 2020+: no se pueden lanzar apps** con la integración nativa (endpoint REST removido). Zapping por `remote.send_command KEY_*` sí funciona. Apps → HACS `ha-samsungtv-smart` si algún día hace falta.
3. **El picker de Atajos de iOS (App Intents) solo lista ciertos dominios** — scripts no aparecen; por eso los switches template. Su caché tarda en refrescar (reabrir app HA / reiniciar iPhone).
4. **Entidades fantasma del LG**: si la integración webostv se re-parea, HA puede resucitar entidades viejas con sufijo `_2`. Limpiar por WebSocket API (`config/entity_registry/remove` + `update`), no editando `.storage` a mano.

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 1 — Base | R2130 + Docker + HA + MQTT + TVs + iPhone + Tailscale + backups | ✅ 2026-09-19 |
| 1.5 — Extras | house_mode, WoL, apps/canales, Siri (HomeKit bridge) | ✅ 2026-09-19 |
| 2 — Presencia | SLZB-06M + Zigbee2MQTT, sensor puerta, mmWave, llegada/salida reales | ⏳ espera compra USA |
| 3 — Living | Shelly Dimmer (electricista), ESP32 IR → NAD + aire, Modo Cine | ⏳ |
| 4 — Cámara + AI | HailoRT 4.21 + Frigate + Reolink, person/dog, modo CLEANING | ⏳ |
| 5 — Voz + audio | Voice PE, Music Assistant → USB-S/PDIF → NAD | ⏳ |

BOM de compra USA (verificado sept-2026, ~USD 505-545): ver la spec, sección BOM.
