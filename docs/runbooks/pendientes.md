# Pendientes

- Reservar IP 192.168.1.17 (R2130) y la IP de la LG (192.168.1.14) en el DHCP del router.
- Dominio neuralcore.dev (Cloudflare) disponible: decidimos NO exponer HA públicamente por ahora
  (Tailscale cubre acceso remoto sin superficie de ataque). Reabrir solo si Tailscale molesta en
  el iPhone (conflicto con otro VPN) o si hay que dar acceso a terceros → Cloudflare Tunnel + Access.
- Acceso remoto a HA para geofence en tiempo real (Fase 2): evaluar
  Nabu Casa Cloud (USD 6.50/mes, financia el proyecto HA) vs Tailscale (gratis).
- Fase 4: verificar versión HailoRT del host vs la requerida por Frigate (4.21.0 para 0.16).
