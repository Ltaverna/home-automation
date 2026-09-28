# Estado actual — inventario vivo

> Actualizado: 2026-09-28. Actualizar este documento cuando se agregue/quite hardware,
> integraciones, scripts o automatizaciones.

## Hardware en producción

| Equipo | IP | Detalle |
|---|---|---|
| reComputer AI R2130 | 192.168.1.17 | Pi 5 8GB, Hailo-8 26 TOPS (`/dev/hailo0`), NVMe 512GB, Pi OS Bookworm 64. Corre además un crypto-bot en `/opt/crypto-bot` (cron 04:00) — no tocar |
| LG OLED55C3PSA (living) | 192.168.1.14 | webOS por LAN. WoL MAC `38:06:E6:1C:26:70`. Óptico → NAD D3020 V2 + Dynaudio Emit M10. ⚠ El volumen real del living lo maneja el NAD (salida óptica de la TV es nivel fijo): los controles de volumen del LG en HA no afectan lo que suena; control real de volumen vía ESP32 IR en Fase 3 |
| Samsung QLED Q60T (dormitorio) | 192.168.1.16 | Tizen por LAN. WoL MAC `68:72:C3:80:C4:A8`. HDMI eARC → Sony HT-G700 (la barra no tiene red; volumen/power vía CEC) |
| iPhone 15 Pro Max | tailnet `100.86.243.112` | HA Companion (geofence) + Tailscale |

Pendiente de instalación (sin comprar aún): NAD D3020 V2 (IR, Fase 3), aire split sin WiFi (IR, Fase 3), cerradura Philips DDL615 (autónoma, sin integración por decisión — ver spec §DDL615).

### NAD D3020 V2 — mapa de entradas (living)

| Entrada | Fuente | Estado |
|---|---|---|
| Optical | LG OLED C3 (TV/streaming) | en uso |
| Bluetooth (aptX) | Spotify desde el teléfono | en uso |
| Phono | bandeja de vinilos | en uso |
| Coaxial | R2130 vía USB→S/PDIF (Music Assistant/Squeezelite) | Fase 5 |

En Fase 3 el ESP32 IR le da a HA: power, volumen (el real del living), mute y
**selección de fuente** — o sea escenas tipo "modo vinilo" (Phono), "modo cine"
(Optical) o "música" (Coax) van a ser posibles.

## Integraciones activas en HA

| Integración | Config | Notas |
|---|---|---|
| MQTT | `localhost:1883`, usuario `ha` | password en `.env` de la R2130 |
| LG webOS TV | 192.168.1.14 | entidad `media_player.lg_webos_tv_oled55c3psa` |
| Samsung TV (HACS `samsungtv_smart` 0.14.5 + SmartThings) | 192.168.1.16 | `media_player.tv_dormitorio` + `remote.tv_dormitorio`. Teclas/power/dígitos: local (ws). Apps: SOLO vía cloud SmartThings (`rest_command.st_tv_dormitorio_app`, token en `secrets.yaml` de la R2130) — Samsung capó el ws local en 2020+. IDs capturados: Flow=`fCCrJTSe28.Flow`, Netflix=`org.tizen.netflix-app`, YouTube=`9Ur5IzDKqV.TizenYouTube` |
| Mobile App | Lucas's iPhone | `person.lucas`, `notify.mobile_app_lucass_iphone` |
| HomeKit Bridge "HASS Bridge" | puerto 21063 | expone los 6 switches de apps (sala + dormitorio) a Apple Home / Siri |
| HomeKit accessory "TV Sala" | puerto 21064 | el LG como TV HomeKit → remote del Centro de Control de iOS (teclas mapeadas por la automatización `homekit_remote_lg`) |
| HACS | instalado, **sin configurar** | login GitHub pendiente; gestiona `samsungtv_smart` |
| Bluetooth | adaptador interno R2130 | disponible para BLE futuro |
| Tailscale (host, no HA) | `tailscale serve` → 8123 | `https://r2130.tail71f19f.ts.net` |
| FaceEmbed API (`face-embed`, experimental) | contenedor, puerto 8000 | Reconocimiento facial en Hailo-8 (SCRFD + ArcFace, embedding 512-d ~11ms). HailoRT 4.20 dockerizado (no toca el host). DB SQLite en `face-embed/data/`. Scripts en `face-embed/scripts/`. Ver [`referencia-arcface.md`](referencia-arcface.md) |
| face-recognizer (`face-recognizer`) | contenedor, loop ~4s | Captura `/dev/video0` (Redragon) → face-embed → MQTT. Crea `sensor.ultima_cara` (lucas/desconocido/nadie) por Discovery. Alimenta notif + `input_boolean.lucas_visto_camara` (señal blanda). **Pausado por defecto** |
| healthmon (`healthmon`) | contenedor, loop ~60s | Health-checks HTTP a face-embed/MCP/HA → `binary_sensor.salud_*` por MQTT Discovery. Pinguea healthchecks.io (dead-man switch) si HA OK. Vista "Salud" en el dashboard + automatización `salud_alerta` |
| MCP Server (`mcp_server`, nativo) | API "assist", endpoint `/mcp_server/sse` | Solo transporte SSE legacy → **incompatible con ChatGPT** (exige streamable HTTP). Sigue activo pero SIN uso; el túnel ya no lo apunta. Sirve por LAN/Tailscale para clientes que toleren SSE |
| **HA-MCP** (HACS `ha_mcp_tools` 8.5.0) | puerto **9584**, secret_path | El MCP en uso para la nube. Streamable HTTP moderno (protocolo 2025-06-18) + OAuth/DCR → compatible con ChatGPT **y** Claude. Expuesto por el túnel `ha-mcp.neuralcore.dev` → `:9584`. Credencial = **secret_path** aleatorio (modo `webhook_auth: ha_auth` configurado, pero el secret_path da acceso directo). La URL con el secret_path es una credencial → NO va a git (está en la config entry / backup). `llm_api_exposure: both` |

## Entidades y helpers clave

- `input_select.house_mode` — `HOME / AWAY / CLEANING / NIGHT` (CINEMA será escena)
- `person.lucas` — geofence del iPhone (tiempo real gracias a Tailscale)
- `switch.flow_sala` / `switch.netflix_sala` / `switch.youtube_sala` — template switches:
  ON = encender TV (WoL) + abrir app · OFF = apagar TV · estado refleja el source real
- `switch.flow_dormitorio` / `switch.netflix_dormitorio` / `switch.youtube_dormitorio` — ídem
  para el Samsung (lanzan vía SmartThings). Los 6 expuestos a Siri por HomeKit Bridge.
- `input_boolean.modo_paseo` — paseo del perro; suspende AWAY 30 min (timer `timer.paseo`)
- `input_boolean.modo_simulacion` — "modo vacío" anti-robo. Ambos expuestos a Siri (HomeKit)
- `sensor.ultima_cara` — último reconocido por la cámara (vía MQTT); atributos `similarity`, `visto`
- `input_boolean.lucas_visto_camara` — señal blanda: Lucas visto por cámara (no cambia house_mode solo)
- `binary_sensor.salud_face_embed` / `salud_mcp` / `salud_home_assistant` — salud de servicios (device_class problem; off=ok, on=problema)
- `sensor.node_cpu` / `node_ram` / `node_temp_cpu` / `node_temp_nvme` / `node_disk` + `binary_sensor.node_nvme_smart` — métricas del host R2130 (device "Nodo R2130"), publicadas cada ~1 min por `scripts/node-metrics.sh` (cron root). La temp del Hailo-8 no se expone (no hay hwmon/hailortcli on-demand); se muestra la del NVMe
- Scripts nuevos dormitorio: `tv_app_dormitorio` (param `app_id`), `flow_dormitorio`,
  `netflix_dormitorio`, `youtube_dormitorio`; `flow_canal_dormitorio` ahora abre Flow solo.
- Gotcha operativo: tras un restart de HA, si el Samsung reporta estados raros
  (off estando prendida, app None), recargar la config entry de samsungtv_smart.

## Scripts

> Config modularizada (2026-09-28): scripts, automatizaciones y helpers viven en
> `homeassistant/packages/<feature>.yaml` (tv, house_mode, paseo, seguridad, face, salud).
> `automations.yaml`/`scripts.yaml` quedaron vacíos. Los entity_id no cambiaron.

### Sala (LG)

| Script | Qué hace |
|---|---|
| `tv_living_encender` | Magic packet WoL al LG |
| `tv_app` (param `app`) | Enciende si hace falta, espera boot, abre la app por nombre del `source_list` |
| `flow_sala` / `netflix_sala` / `youtube_sala` | Atajos sin parámetros sobre `tv_app` |
| `flow_canal` (param `canal` o `nombre`) | Abre Flow y zapea con dígitos + ENTER. Acepta número (`canal: 14`) o nombre (`nombre: tn`). **Grilla Flow AMBA cargada (~55 canales + alias); validado en vivo (LG acepta dígitos con Flow reproduciendo, no necesita ir a la Guía)** |

### Dormitorio (Samsung)

| Script | Qué hace |
|---|---|
| `tv_dormitorio_encender` | Magic packet WoL al Samsung |
| `tv_app_dormitorio` (param `app_id`) | Enciende si hace falta, espera boot, lanza la app por su ID Tizen vía SmartThings (`rest_command`) |
| `flow_dormitorio` / `netflix_dormitorio` / `youtube_dormitorio` | Atajos sin parámetros sobre `tv_app_dormitorio` con los IDs Tizen |
| `flow_canal_dormitorio` (param `canal`) | Abre Flow, navega a la Guía (abajo, abajo, derecha, ENTER) y tipea el canal + ENTER vía `remote.send_command`. Ruta mapeada de la app Flow del Samsung |

### General

| Script | Qué hace |
|---|---|
| `iniciar_paseo` | Apaga ambas TVs, arranca `timer.paseo` (30 min) y notifica; lo dispara `modo_paseo_inicio` |

### Host (fuera de HA, por cron)

| Script | Qué hace |
|---|---|
| `scripts/node-metrics.sh` | Cron root cada 1 min → `/var/log/node-metrics.log`. Publica métricas del host (CPU, RAM, temp CPU, temp NVMe, disco `/`, SMART NVMe) a MQTT Discovery (device "Nodo R2130"). PATH explícito porque `smartctl` vive en `/usr/sbin` (fuera del PATH de cron). Métricas del host (no de un contenedor sin privilegios), coherente con `healthmon` |

## Automatizaciones

| ID | Función |
|---|---|
| `tv_living_wol` | Hook `webostv.turn_on` → WoL (el LG en deep-off no responde por webOS) |
| `house_mode_llegada` | iPhone → home ⇒ HOME + notificación. Fase 2: sumar confirmación por puerta |
| `house_mode_salida` | not_home 5 min ⇒ AWAY + apagar TVs + notificación. Respeta CLEANING **y modo_paseo** (no dispara si estás paseando). Fase 2: sumar mmWave |
| `house_mode_noche_provisional` | 23:30 en casa ⇒ NIGHT. Fase 2: presencia real en dormitorio |
| `house_mode_manana` | 07:00 si NIGHT ⇒ HOME |
| `despertar_suave` | 08:30 L-V estando en casa → TV dormitorio en Flow canal 14 |
| `modo_paseo_inicio` / `modo_paseo_fin` | Paseo del perro: apaga TVs + timer 30 min; suspende AWAY; se cierra por timer o al volver a home |
| `aviso_tv_prendida_sin_nadie` / `aviso_tv_accion_apagar` | Estando AWAY con TV encendida 2 min → notif accionable (long-press muestra "Apagar"); `not modo_simulacion` |
| `simulacion_toggle_tv_living` / `simulacion_apagar_a_las_23_30` | Modo simulación + AWAY, 19-23:30: togglea el LG al azar (50% cada 30 min); apaga a las 23:30 |
| `face_reconocido` / `face_lucas_presencia` | Notif al reconocer (o cara desconocida); prende/apaga `lucas_visto_camara` (señal blanda) |
| `salud_alerta` | Notif al iPhone cuando un servicio no-core cae/recupera (transición) |
| `nodo_alerta` | Notif accionable de salud del host: disco `/` > 85% (5 min), temp CPU > 80 °C (2 min) o SMART del NVMe en falla |

## Control desde el iPhone

1. **Siri nativo:** app Casa → "Oye Siri, enciende Flow sala / Netflix dormitorio / ..."
   (los 6 switches). Solo en LAN (no hay hub Apple TV/HomePod — decisión: no comprar).
2. **Remote del Centro de Control de iOS:** deslizar → ícono remoto → "TV Sala" → pad táctil
   para navegar el LG (perfil de YouTube, menús). 100% nativo Apple.
3. **App HA → dashboard "Control remoto":** d-pad + dígitos + apps + volumen para ambas TVs;
   funciona también fuera de casa (Tailscale).

(Los webhooks para Atajos iOS se eliminaron el 2026-09-28: redundantes con HomeKit/MCP y sus
IDs eran credenciales en git. El control por voz/remoto ya está cubierto por Siri + HomeKit + MCP.)

## Accesos y secretos (nada de esto está en git)

- SSH: alias `r2130` en el mini-PC (`pi@192.168.1.17`, clave `~/.ssh/minipc-to-raspi5`)
- Token API HA: `~/.ha_token` en el mini-PC
- `.env` + `mosquitto/config/passwd` + `homeassistant/.storage`: solo en la R2130 y en el backup nocturno (`/opt/backups/home-automation/`, 04:30, retiene 14)
- Deploy key GitHub read-only en la R2130
- `homeassistant/secrets.yaml` (fuera de git): `st_bearer`, `st_url`, `lg_mac`, `samsung_mac`.
  Plantilla versionada en `secrets.yaml.example`. Los packages los usan con `!secret`.
- `COMPOSE_PROFILES` en `.env` (casa principal: `face,obs`) — define qué servicios levantan.
- Backups (dos capas): (1) local 04:30 → `/opt/backups` (tar, 14 días); (2) off-site 04:45 →
  Cloudflare R2 con restic (cifrado, incremental, 7d/4w/6m). Credenciales en `.restic-env` (600,
  fuera de git). Restore verificado. La `RESTIC_PASSWORD` está fuera del R2130 (imprescindible).

## Pendientes

Ver [`runbooks/pendientes.md`](runbooks/pendientes.md) — abiertos, decisiones registradas
y resueltos con fecha.
