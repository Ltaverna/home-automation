# Spec: Domótica depto — nodo único reComputer R2130

**Fecha:** 2026-09-19
**Estado:** aprobado
**Basado en:** `docs/arquitectura-domotica-home-assistant-lucas-v4.md` (documento ChatGPT v4), con las modificaciones decididas en la sesión de brainstorming.

## Contexto

Departamento, un solo ocupante (Lucas) + perro + limpieza periódica (martes).
Hardware existente: **Seeed reComputer AI R2130** (Raspberry Pi 5 8GB + Hailo-8 26 TOPS + SSD), mini-PC disponible pero **no se usa** (queda de respaldo). TV LG OLED55C5PSA, amplificador NAD D3020 V2 (LG→NAD por óptico), aire acondicionado split común **sin WiFi** (solo IR), cerradura Philips DDL615-5HBS (autónoma, sin integración). Teléfono: iPhone.

Filosofía (heredada del doc v4, se mantiene): local-first, simple, confiable, usable manualmente aunque HA falle. Regla de diseño por dispositivo: API local → Zigbee/Matter → ESPHome → IR/RF → cloud como último recurso.

## Decisiones tomadas (difieren del doc v4)

1. **Nodo único**: todo corre en la R2130. El doc v4 asumía mini-PC para HA + Raspi como edge AI; se descarta el segundo equipo. Para 1-2 cámaras la R2130 sobra y se elimina un punto de falla.
2. **Pi OS 64-bit + Docker Compose** (no HAOS): máxima flexibilidad para servicios AI propios sobre el Hailo; todo el árbol de configs versionado en este repo.
3. **Coordinador Zigbee: SMLIGHT SLZB-06M** por Ethernet (no ZBT-2 USB): ubicación independiente del servidor, sin interferencia USB, encaja con Zigbee2MQTT + Mosquitto.
4. **Aire por IR** (ESP32 + ESPHome): confirmado split sin WiFi.
5. **Compra USA completa** (imprescindible + recomendable de una vez): ~USD 505-545.
6. **Fases reordenadas**: Fase 1 es puro software (sin compras); Zigbee/presencia antes que cámara/Frigate.

## Arquitectura

```text
                    Router / WiFi
                         │
        ┌────────────────┼──────────────────┐
        │                │                  │
  reComputer R2130   SLZB-06M          LG OLED C5 (LAN/webOS)
  (Pi OS + Docker)   (Zigbee/Ethernet)      │ optical
        │                │                  ▼
        │            puerta, mmWave,   NAD D3020 V2
        │            temp, botones          ▲
        │                                   │ IR
        ├── cámara PoE (entrada)       ESP32 ESPHome ──► Aire (IR)
        └── USB→S/PDIF → NAD coaxial
```

## Stack de software

Docker Compose en `/opt/home-automation/docker-compose.yml`:

| Servicio | Imagen base | Rol |
|---|---|---|
| `homeassistant` | HA Container | Automatizaciones, escenas, house modes, dashboards, integración webOS |
| `mosquitto` | eclipse-mosquitto | Broker MQTT |
| `zigbee2mqtt` | koenkk/zigbee2mqtt | Red Zigbee vía SLZB-06M (TCP/Ethernet) |
| `frigate` | ghcr.io/blakeblackshear/frigate | NVR + detección `person`/`dog`, detector `hailo8`, go2rtc interno |
| `esphome` | esphome/esphome | Compilar/flashear ESP32 IR |
| `music-assistant` | music-assistant/server | Servidor de música |
| `squeezelite` | squeezelite | Endpoint audio → USB→S/PDIF → NAD coaxial |

Host:
- Raspberry Pi OS 64-bit (Bookworm o posterior), boot desde SSD.
- Driver **HailoRT 4.21.0** instalado con el script oficial de Frigate (`user_installation.sh`), **no** el paquete apt de Pi OS (evita mismatch driver host ↔ librería contenedor; Frigate 0.16 requiere 4.21.0).
- Posible ajuste PCIe `force_desc_page_size` en Pi 5 (documentado por Jeff Geerling).
- Red por Ethernet, IP fija o reserva DHCP.
- Backups: snapshot nocturno (cron) de los directorios de config a tar en el SSD + repo git pusheado a GitHub. Secretos en `.env`, fuera de git.

## Presencia y house modes

Estados globales (`input_select.house_mode`): `HOME / AWAY / CLEANING / NIGHT`. `CINEMA` es escena, no estado.

Señales:
- iPhone (geofence HA companion) → `person.lucas`
- Sensor puerta Zigbee (Aqara MCCGQ11LM) → `binary_sensor.puerta_entrada`
- mmWave living (Everything Presence Pro/One) → presencia por zona (sofá/mesa/TV)
- Frigate + Hailo → `person` / `dog` en zona de entrada

Reglas clave (heredadas del doc v4 §41-51, se mantienen tal cual):
- El perro genera `dog_present`, nunca cambia la casa a HOME. No usar `PIR = HOME`.
- HOME = iPhone HOME + puerta abierta recientemente (confirmación opcional).
- AWAY = iPhone AWAY + `human_present=false` + no CLEANING. No apagar todo ante un único cambio de geofence.
- CLEANING (inferido, la cerradura no reporta PIN): Lucas AWAY + `schedule.limpieza` ON + puerta se abre + `human_present=true`. Comportamiento: luces automáticas fuertes, clima si hace falta, sin alertas normales; nunca Modo Cine/TV/NAD automáticos. Salida: puerta cerrada + sin humano N minutos → AWAY.
- Cerradura DDL615: autónoma. Controla ACCESO; HA controla CONTEXTO. No comprar gateway Philips ni ESP32 BLE dedicado. Nunca unlock automático por sensores.

Escenas/automatizaciones objetivo: Llegada, Salida, Modo Cine (sofá + TV on + luz baja → living 15%, NAD Optical, aire si >26°C), Modo Noche, Despertar.

## BOM — compra USA (precios verificados sept 2026)

| Ítem | Precio USD | Dónde |
|---|---|---|
| SMLIGHT SLZB-06M | 40 | CloudFree |
| Everything Presence Pro (living) ⚠ backorder, envío est. 5-oct | 85-90 | shop.everythingsmart.io |
| HA Voice Preview Edition | 59 | ameriDroid / CloudFree |
| Reolink RLC-810A (PoE, entrada) | 90-110 | Amazon |
| PoE injector TP-Link TL-PoE150S | 18 | Amazon |
| Shelly Dimmer Gen3 (220-240V, sirve AR) | 30-35 | Amazon |
| Shelly 1PM Gen3 ×2 | 30 | us.shelly.com |
| Shelly Bypass (contingencia sin neutro) | 10 | Amazon |
| Aqara puerta MCCGQ11LM | 18 | Amazon |
| Aqara temp/hum WSDCGQ11LM | 20 | Amazon |
| ESP32 ×3 + LEDs IR 940nm + transistores | 30 | Amazon |
| Douk Audio U2 (USB→S/PDIF coaxial) | 45 | Amazon |
| Mini DC UPS (5/9/12V) | 30 | Amazon |
| **Total** | **~505-545** | |

Contingencia: si la compra es antes de octubre, reemplazar Presence Pro por **Everything Presence One (USD 64)**.

En Argentina: lámparas LED **dimerizables** (etiqueta DIMMABLE/REGULABLE), cables, electricista para relevar fase/neutro/retornos/profundidad de cajas **antes** de instalar Shelly (doc v4 §40).

No comprar (confirmado): Google Coral, gateway Philips, switch PoE grande, múltiples cámaras, hubs propietarios, dispositivos Matter sin necesidad.

## Fases de implementación

1. **Base (sin compras, arranca ya)** — Pi OS + Docker + repo + HA + Mosquitto + integración LG webOS + app companion iPhone.
2. **Zigbee + presencia** — SLZB-06M + Zigbee2MQTT, sensor puerta, mmWave, house modes, automatizaciones llegada/salida/noche.
3. **Living** — Shelly Dimmer + 1PM (con electricista), ESP32 IR (NAD + aire), Modo Cine.
4. **Cámara + AI** — HailoRT 4.21.0, Frigate, Reolink en entrada, person/dog, modo CLEANING completo.
5. **Voz + audio** — Voice PE, Music Assistant, Squeezelite + USB→S/PDIF al NAD, Despertar con música.

Cada fase termina con sus automatizaciones probadas y la config commiteada.

## Estructura del repo

```text
/opt/home-automation/
├── docker-compose.yml
├── .env                    # secretos — NO va a git (.gitignore)
├── homeassistant/          # configuration.yaml, automations/, scenes/
├── mosquitto/
├── zigbee2mqtt/
├── frigate/
├── esphome/                # ir-living.yaml (NAD + aire), futuros nodos
└── docs/
    ├── arquitectura-domotica-home-assistant-lucas-v4.md
    ├── superpowers/specs/  # esta spec
    └── runbooks/           # instalación, backups, recovery
```

## Manejo de errores / resiliencia

- Teclas físicas siguen funcionando con Shelly aunque HA esté caído.
- Cerradura y aire operables manualmente siempre.
- Contenedores con `restart: unless-stopped`; healthcheck de HA.
- Mini UPS para la R2130 + router (cortes breves).
- Config recuperable: `git clone` + `.env` + `docker compose up` sobre un Pi OS limpio (runbook de recovery en docs/).

## Criterios de éxito

- Fase 1: HA accesible en LAN, controla la LG (power/volumen/apps), iPhone trackeado.
- Fase 2: llegada/salida/noche funcionan una semana sin falsos positivos (el perro no dispara HOME).
- Fase 3: Modo Cine end-to-end desde presencia en sofá; luces dimerizables sin parpadeo.
- Fase 4: Frigate distingue person/dog en entrada; CLEANING se activa/desactiva solo los martes.
- Fase 5: "modo cine" y "apagá todo" por voz; música de Music Assistant suena en el NAD.
