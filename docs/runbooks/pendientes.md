# Pendientes

- HECHO 2026-09-19: LG C3 re-pareada (`media_player.lg_webos_tv_oled55c3psa`, 192.168.1.14) y
  Samsung Q60T dormitorio integrada (`media_player.lucass_tv_60ta`, 192.168.1.16,
  MAC 68:72:C3:80:C4:A8 para WoL). Sony HT-G700: sin red, se controla indirecto por
  HDMI-CEC a través del Samsung. Reservar también la IP de la Samsung en el router.
- Samsung Q60T: la integración nativa no lanza apps en modelos 2020+ (endpoint REST removido).
  Si se quiere "poné Netflix" en el dormitorio: integración HACS ollo69/ha-samsungtv-smart
  (apps vía SmartThings). Zapping de canales ya resuelto con remote.send_command KEY_*.
- Cargar grilla Flow nombre→número en script.flow_canal (dictada por Lucas desde la guía).
- Probar encendido remoto de ambas TVs con las TVs apagadas (LG: Quick Start+ activado;
  Samsung: WoL). Si el LG no enciende, fallback wake_on_lan documentado en el plan Fase 1.

- Reservar IP 192.168.1.17 (R2130) y la IP de la LG (192.168.1.14) en el DHCP del router.
- Dominio neuralcore.dev (Cloudflare) disponible: decidimos NO exponer HA públicamente por ahora
  (Tailscale cubre acceso remoto sin superficie de ataque). Reabrir solo si Tailscale molesta en
  el iPhone (conflicto con otro VPN) o si hay que dar acceso a terceros → Cloudflare Tunnel + Access.
- Acceso remoto a HA para geofence en tiempo real (Fase 2): evaluar
  Nabu Casa Cloud (USD 6.50/mes, financia el proyecto HA) vs Tailscale (gratis).
- Fase 4: verificar versión HailoRT del host vs la requerida por Frigate (4.21.0 para 0.16).
