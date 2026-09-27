# Runbook: onboarding de una casa nueva

Cómo levantar una instancia independiente del sistema en otra casa. El repo es la base común;
cada casa tiene su propio `.env`, `secrets.yaml`, dispositivos y túnel Cloudflare.

## 1. Sistema base
Seguir [`instalacion-r2130.md`](instalacion-r2130.md): Pi OS 64-bit + Docker + `git clone` del
repo en `/opt/home-automation` (deploy key read-only propia de esa casa).

## 2. Secretos y perfiles
- `cp .env.example .env` y completar: `TZ`, `MQTT_USER`/`MQTT_PASSWORD`, `HEALTHCHECKS_URL`,
  `COMPOSE_PROFILES` (`face,obs` si hay Hailo+cámara; `obs` o vacío si no).
- `cp homeassistant/secrets.yaml.example homeassistant/secrets.yaml` y completar `st_bearer`,
  `st_url`, `lg_mac`, `samsung_mac` con los valores de esta casa.
- Crear el `passwd` de Mosquitto (ver instalacion-r2130.md).

## 3. Levantar
`cd /opt/home-automation && docker compose up -d` (levanta según `COMPOSE_PROFILES`).

## 4. Home Assistant: onboarding + dispositivos
- Onboarding en `http://<ip>:8123`, crear usuario admin.
- Integrar MQTT (localhost:1883, user/pass del `.env`).
- Parear las TVs y **renombrar las entidades** para que coincidan con las que usan los packages
  (convención de nombres). Entity IDs esperados por los packages:
  - LG webOS: `media_player.lg_webos_tv_oled55c3psa`
  - Samsung (samsungtv_smart): `media_player.tv_dormitorio` + `remote.tv_dormitorio`
  - Si los modelos difieren, o renombrás el entity_id tras el pairing
    (Settings → Entities → ⚙ → Entity ID), o editás los packages para usar el nombre real.

## 5. Recapturar lo casa-específico (no parametrizable)
- **MACs WoL** → `secrets.yaml` (`lg_mac`, `samsung_mac`): `ip neigh show <ip-tv>` o la etiqueta de la TV.
- **device_id SmartThings** → `secrets.yaml` (`st_url`):
  `curl -H "Authorization: Bearer <token>" https://api.smartthings.com/v1/devices` → armar la URL.
- **IDs Tizen de las apps del Samsung** (en `packages/tv.yaml`, switches + scripts `*_dormitorio`):
  abrir cada app en la TV y leer el atributo `app_id` de `media_player.tv_dormitorio` (método del
  PoC de face rec: se ve en Developer Tools → States).
- **Grilla Flow** (`packages/tv.yaml`, diccionario `grilla`): varía por zona; cargar la de la casa
  y corregir contra la TV real a medida que se usa.

## 6. Acceso remoto (Cloudflare + MCP) — propio de cada casa
- Crear un túnel propio: `cloudflared tunnel create ha-mcp-<casa>` + `cloudflared tunnel route dns`
  a un subdominio propio.
- Ajustar `cloudflared/config-mcp.yml` (tunnel id + hostname) y `external_url` en
  `configuration.yaml`. Copiar el credentials JSON del túnel a `cloudflared/` (fuera de git).
- Activar la integración `ha_mcp_tools`; el secret_path se genera solo (queda en `.storage`).

## 7. Verificar
- `docker exec homeassistant python -m homeassistant --script check_config -c /config`.
- Vista "Salud" (si profile `obs`): servicios en verde.
- Encender una TV por WoL y lanzar una app (valida `!secret` de MAC y `st_url`).

## Lo que NO se copia entre casas (es de cada instancia, no del repo)
`.env`, `homeassistant/secrets.yaml`, `homeassistant/.storage` (pairings/tokens/entity registry),
`cloudflared/*.json`, la DB de caras (`face-embed/data/`), y el subdominio/túnel Cloudflare.
El repo aporta la **lógica** (packages, scripts, compose); cada casa aporta su **contexto**.
