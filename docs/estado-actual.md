# Estado actual — inventario vivo

> Actualizado: 2026-09-19. Actualizar este documento cuando se agregue/quite hardware,
> integraciones, scripts o automatizaciones.

## Hardware en producción

| Equipo | IP | Detalle |
|---|---|---|
| reComputer AI R2130 | 192.168.1.17 | Pi 5 8GB, Hailo-8 26 TOPS (`/dev/hailo0`), NVMe 512GB, Pi OS Bookworm 64. Corre además un crypto-bot en `/opt/crypto-bot` (cron 04:00) — no tocar |
| LG OLED55C3PSA (living) | 192.168.1.14 | webOS por LAN. WoL MAC `38:06:E6:1C:26:70`. Óptico → NAD D3020 V2 + Dynaudio Emit M10. ⚠ El volumen real del living lo maneja el NAD (salida óptica de la TV es nivel fijo): los controles de volumen del LG en HA no afectan lo que suena; control real de volumen vía ESP32 IR en Fase 3 |
| Samsung QLED Q60T (dormitorio) | 192.168.1.16 | Tizen por LAN. WoL MAC `68:72:C3:80:C4:A8`. HDMI eARC → Sony HT-G700 (la barra no tiene red; volumen/power vía CEC) |
| iPhone 15 Pro Max | tailnet `100.86.243.112` | HA Companion (geofence) + Tailscale |

Pendiente de instalación (sin comprar aún): NAD D3020 V2 (IR, Fase 3), aire split sin WiFi (IR, Fase 3), cerradura Philips DDL615 (autónoma, sin integración por decisión — ver spec §DDL615).

## Integraciones activas en HA

| Integración | Config | Notas |
|---|---|---|
| MQTT | `localhost:1883`, usuario `ha` | password en `.env` de la R2130 |
| LG webOS TV | 192.168.1.14 | entidad `media_player.lg_webos_tv_oled55c3psa` |
| Samsung TV | 192.168.1.16 | `media_player.lucass_tv_60ta` + `remote.lucass_tv_60ta` |
| Mobile App | Lucas's iPhone | `person.lucas`, `notify.mobile_app_lucass_iphone` |
| HomeKit Bridge | puerto 21063 | expone los 3 switches de apps a Apple Home / Siri |
| Bluetooth | adaptador interno R2130 | disponible para BLE futuro |
| Tailscale (host, no HA) | `tailscale serve` → 8123 | `https://r2130.tail71f19f.ts.net` |

## Entidades y helpers clave

- `input_select.house_mode` — `HOME / AWAY / CLEANING / NIGHT` (CINEMA será escena)
- `person.lucas` — geofence del iPhone (tiempo real gracias a Tailscale)
- `switch.flow_sala` / `switch.netflix_sala` / `switch.youtube_sala` — template switches:
  ON = encender TV (WoL) + abrir app · OFF = apagar TV · estado refleja el source real

## Scripts

| Script | Qué hace |
|---|---|
| `tv_living_encender` / `tv_dormitorio_encender` | Magic packet WoL a cada TV |
| `tv_app` (param `app`) | LG: enciende si hace falta, espera boot, abre la app (nombres del source_list) |
| `flow_sala` / `netflix_sala` / `youtube_sala` | Atajos sin parámetros sobre `tv_app` |
| `flow_canal` (param `canal` o `nombre`) | LG: zapping en Flow — dígitos + ENTER. Grilla nombre→número en el propio script (**incompleta: solo telefe=10, falta que Lucas dicte la suya**) |
| `flow_canal_dormitorio` (param `canal`) | Samsung: dígitos + ENTER vía `remote.send_command KEY_*`. Requiere Flow ya abierto |

## Automatizaciones

| ID | Función |
|---|---|
| `tv_living_wol` | Hook `webostv.turn_on` → WoL (el LG en deep-off no responde por webOS) |
| `house_mode_llegada` | iPhone → home ⇒ HOME + notificación. Fase 2: sumar confirmación por puerta |
| `house_mode_salida` | not_home 5 min ⇒ AWAY + apagar TVs + notificación. Respeta CLEANING. Fase 2: sumar mmWave |
| `house_mode_noche_provisional` | 23:30 en casa ⇒ NIGHT. Fase 2: presencia real en dormitorio |
| `house_mode_manana` | 07:00 si NIGHT ⇒ HOME |
| `webhook_flow_sala` / `_netflix_sala` / `_youtube_sala` | POST sin auth (IDs aleatorios = secreto) para Atajos iOS; solo alcanzables desde la tailnet |

## Control desde el iPhone

1. **Siri nativo (recomendado):** HomeKit Bridge → app Casa → "Oye Siri, enciende Flow sala".
   Solo en LAN (no hay hub Apple TV/HomePod).
2. **App HA:** tarjetas de TVs + switches + scripts; funciona también fuera de casa (Tailscale).
3. **Atajos por webhook (plan C):** POST a `https://r2130.tail71f19f.ts.net/api/webhook/<id>`
   (IDs en `automations.yaml`). Funciona fuera de casa con Tailscale activo.

## Accesos y secretos (nada de esto está en git)

- SSH: alias `r2130` en el mini-PC (`pi@192.168.1.17`, clave `~/.ssh/minipc-to-raspi5`)
- Token API HA: `~/.ha_token` en el mini-PC
- `.env` + `mosquitto/config/passwd` + `homeassistant/.storage`: solo en la R2130 y en el backup nocturno (`/opt/backups/home-automation/`, 04:30, retiene 14)
- Deploy key GitHub read-only en la R2130

## Verificaciones pendientes de la vida real

- Primera salida/llegada real del depto (notificaciones AWAY/HOME y timing del geofence)
- Activar Quick Start+ en el LG para que quede accesible en standby (hoy queda `unavailable`
  al apagarse; el WoL funciona igual)
- Dictar la grilla de canales Flow para `flow_canal`
