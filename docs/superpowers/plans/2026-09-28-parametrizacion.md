# Parametrización casa-específica — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aislar los valores casa-específicos (secrets.yaml + compose profiles) y dejar un doc de onboarding para instalar en una segunda casa, sin cambiar el runtime actual. Según `docs/superpowers/specs/2026-09-28-parametrizacion-design.md`.

**Architecture:** 3 capas — (1) valores movibles a `secrets.yaml` con `!secret`; (2) lo no-parametrizable (entity_ids, IDs Tizen, grilla) se cubre con convención + doc; (3) compose profiles para módulos por casa. La documentación se actualiza en el mismo ciclo (MUST).

**Tech Stack:** HA `!secret`, Docker Compose profiles, YAML.

**Regla de oro:** el sistema debe quedar **idéntico en runtime**. Los `!secret` resuelven a los valores actuales; los profiles se activan en la casa principal para que todo siga levantando igual. Verificar tras cada cambio.

```bash
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
checkcfg() { ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull -q
docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -3
EOF
}
```

---

### Task 1: Secrets a `secrets.yaml` + `secrets.yaml.example`

**Files:**
- Modify (en la R2130, fuera de git): `homeassistant/secrets.yaml`
- Create: `homeassistant/secrets.yaml.example`
- Modify: `homeassistant/packages/tv.yaml`

- [ ] **Step 1: Agregar los secrets en la R2130** (el archivo real, no va a git)

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation
grep -q '^lg_mac:' homeassistant/secrets.yaml || cat >> homeassistant/secrets.yaml <<'YAML'
lg_mac: "38:06:E6:1C:26:70"
samsung_mac: "68:72:C3:80:C4:A8"
st_url: "https://api.smartthings.com/v1/devices/bf18b0f0-0a56-6be5-a574-26ef4efdb123/commands"
YAML
grep -E '^(lg_mac|samsung_mac|st_url|st_bearer):' homeassistant/secrets.yaml | sed 's/:.*/: <set>/'
EOF
```
Expected: las 4 claves presentes (`st_bearer` ya existía; `lg_mac`, `samsung_mac`, `st_url` nuevas).

- [ ] **Step 2: Crear `homeassistant/secrets.yaml.example`** (versionado, sin valores reales)

```yaml
# Plantilla de secrets.yaml — copiar a secrets.yaml (fuera de git) y completar con valores reales.
# Token de SmartThings (account.smartthings.com/tokens, scopes Devices):
st_bearer: "Bearer <token-smartthings>"
# URL completa del device SmartThings de la TV (incluye el deviceId):
st_url: "https://api.smartthings.com/v1/devices/<device-id>/commands"
# MAC para Wake-on-LAN de cada TV:
lg_mac: "AA:BB:CC:DD:EE:FF"
samsung_mac: "AA:BB:CC:DD:EE:FF"
```

- [ ] **Step 3: Usar `!secret` en `packages/tv.yaml`**

En `homeassistant/packages/tv.yaml`, reemplazar los 3 valores hardcodeados:

En `script.tv_living_encender`:
```yaml
      - action: wake_on_lan.send_magic_packet
        data:
          mac: !secret lg_mac
```
En `script.tv_dormitorio_encender`:
```yaml
      - action: wake_on_lan.send_magic_packet
        data:
          mac: !secret samsung_mac
```
En `rest_command.st_tv_dormitorio_app`, reemplazar la línea `url:` por:
```yaml
    url: !secret st_url
```

- [ ] **Step 4: Validar y commit**

```bash
git add homeassistant/secrets.yaml.example homeassistant/packages/tv.yaml
git commit -m "refactor: mover MACs y URL SmartThings a secrets.yaml (parametrización)"
git push
```
Luego `checkcfg`. Expected: `check_config` sin ERROR (resuelve los `!secret`).

- [ ] **Step 5: Verificar runtime idéntico (WoL + app Samsung)**

```bash
# reload no alcanza para rest_command/wake_on_lan → restart
ssh r2130 'docker restart homeassistant' && sleep 45
# WoL living (mirar que el script existe y ejecuta sin error)
curl -sS -m 5 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"script.tv_living_encender"}' $BASE/services/script/turn_on
echo "→ ¿la TV del living encendió? (WoL con MAC desde secret)"
```
Expected: la TV enciende (confirma que `!secret lg_mac` resuelve al valor correcto). El usuario confirma visualmente.

---

### Task 2: Compose profiles

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify (R2130, fuera de git): `.env`

- [ ] **Step 1: Agregar `profiles:` a los servicios pesados**

En `docker-compose.yml`:
- A `face-embed` y `face-recognizer`, agregar `profiles: ["face"]`.
- A `healthmon`, agregar `profiles: ["obs"]`.
- `mosquitto`, `homeassistant`, `cloudflared-mcp` **sin** profile (base, siempre levantan).

Ejemplo (face-embed):
```yaml
  face-embed:
    build: ./face-embed
    container_name: face-embed
    profiles: ["face"]
    restart: unless-stopped
    # ... (resto igual)
```
(igual para `face-recognizer` con `profiles: ["face"]` y `healthmon` con `profiles: ["obs"]`).

- [ ] **Step 2: Fijar `COMPOSE_PROFILES` en el `.env` de la R2130** (para no romper la casa actual)

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation
grep -q '^COMPOSE_PROFILES=' .env || echo 'COMPOSE_PROFILES=face,obs' >> .env
grep '^COMPOSE_PROFILES=' .env
EOF
```
Expected: `COMPOSE_PROFILES=face,obs` (activa face-embed, face-recognizer, healthmon como hasta ahora).

- [ ] **Step 3: Documentar en `.env.example`**

Agregar a `.env.example`:
```text
# Perfiles de servicios a levantar (Docker Compose profiles).
#   face → face-embed + face-recognizer (requieren Hailo + cámara)
#   obs  → healthmon (monitor de salud)
# Base (mosquitto, homeassistant, cloudflared-mcp) siempre levanta.
# Casa principal: face,obs · Casa sin Hailo: obs (o vacío).
COMPOSE_PROFILES=face,obs
```

- [ ] **Step 4: Verificar que compose interpreta bien los profiles**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: compose profiles (face/obs) para módulos por casa"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull -q
echo "=== servicios que levantan con COMPOSE_PROFILES del .env ==="
docker compose config --services
echo "=== aplicar (no debería bajar nada; face-recognizer sigue pausado aparte) ==="
docker compose up -d
docker compose ps --format "{{.Name}}: {{.State}}"
EOF
```
Expected: `docker compose config --services` lista los 6 servicios (profiles activos por `face,obs`). `docker compose ps` muestra mosquitto/homeassistant/face-embed/cloudflared-mcp/healthmon `running` (face-recognizer sigue como estaba: detenido a mano). Nada crítico se cae.

Nota: `face-recognizer` fue pausado a mano antes; con el profile activo `docker compose up -d` podría re-levantarlo. Si se quiere mantener pausado: `docker compose stop face-recognizer` después.

---

### Task 3: Doc de onboarding de casa nueva

**Files:**
- Create: `docs/runbooks/onboarding-casa-nueva.md`

- [ ] **Step 1: Escribir `docs/runbooks/onboarding-casa-nueva.md`**

```markdown
# Runbook: onboarding de una casa nueva

Cómo levantar una instancia independiente del sistema en otra casa. El repo es la base común;
cada casa tiene su propio `.env`, `secrets.yaml`, dispositivos y túnel.

## 1. Sistema base
Seguir `instalacion-r2130.md` (Pi OS 64-bit + Docker + clone del repo en `/opt/home-automation`).

## 2. Configurar los secretos y perfiles
- `cp .env.example .env` y completar: `TZ`, `MQTT_USER`/`MQTT_PASSWORD`, `HEALTHCHECKS_URL`,
  `COMPOSE_PROFILES` (ej. `face,obs` si hay Hailo+cámara; `obs` si no).
- `cp homeassistant/secrets.yaml.example homeassistant/secrets.yaml` y completar
  `st_bearer`, `st_url`, `lg_mac`, `samsung_mac` con los valores de esta casa.
- Crear el `passwd` de mosquitto (ver instalacion-r2130.md).

## 3. Levantar
`cd /opt/home-automation && docker compose up -d` (levanta según `COMPOSE_PROFILES`).

## 4. Home Assistant: onboarding + dispositivos
- Onboarding en `http://<ip>:8123`, crear usuario admin.
- Integrar MQTT (localhost:1883, user/pass del .env).
- Parear las TVs (webOS / samsungtv_smart) y **renombrar las entidades** para que coincidan con
  las que usan los packages (convención de nombres):
  - LG: `media_player.lg_webos_tv_oled55c3psa` (o ajustar los packages al nombre real).
  - Samsung: `media_player.tv_dormitorio` + `remote.tv_dormitorio`.
  - Si en la casa nueva los modelos difieren, renombrar el entity_id tras el pairing
    (Settings → Entities → ⚙ → Entity ID) o editar los packages.

## 5. Recapturar lo casa-específico
- **MACs WoL**: `ip neigh show <ip-tv>` o la etiqueta de la TV → a `secrets.yaml`.
- **IDs Tizen del Samsung** (apps): abrir cada app y leer `media_player.tv_dormitorio` →
  atributo `app_id` (método del PoC); actualizar en `packages/tv.yaml` (switches + scripts).
- **device_id SmartThings**: `curl -H "Authorization: Bearer <token>" https://api.smartthings.com/v1/devices`
  → construir `st_url` en `secrets.yaml`.
- **Grilla Flow**: la de la zona (varía). Actualizar el diccionario en `packages/tv.yaml`.

## 6. Acceso remoto (Cloudflare + MCP)
- Crear un túnel propio: `cloudflared tunnel create ha-mcp-<casa>` + ruta DNS a un subdominio
  propio; ajustar `cloudflared/config-mcp.yml` (tunnel id + hostname) y `external_url` en
  `configuration.yaml`.
- Activar `mcp_server`/`ha_mcp_tools` y regenerar el secret_path (queda en `.storage`).

## 7. Verificar
- `docker exec homeassistant python -m homeassistant --script check_config -c /config`.
- Vista "Salud" (si profile `obs`): servicios en verde.
- Encender una TV por WoL y lanzar una app.

## Lo que NO se copia entre casas (es de cada instancia)
`.env`, `secrets.yaml`, `homeassistant/.storage` (pairings/tokens/entity registry),
`cloudflared/*.json`, DB de caras, y el subdominio/túnel Cloudflare.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/onboarding-casa-nueva.md
git commit -m "docs: runbook de onboarding de casa nueva"
git push
```

---

### Task 4: Actualizar documentación (MUST)

**Files:**
- Modify: `README.md`, `docs/estado-actual.md`, `docs/runbooks/pendientes.md`, `docs/runbooks/instalacion-r2130.md`

- [ ] **Step 1: `README.md`** — en la sección de estructura/gotchas, agregar la nota de secrets/profiles:

En la estructura del repo, ajustar la línea de secrets y agregar profiles:
```markdown
│   ├── secrets.yaml          → st_bearer, st_url, lg_mac, samsung_mac (NO va a git; ver secrets.yaml.example)
```
Y en "Operación diaria" o una nota, agregar:
```markdown
- **Perfiles de servicios**: `COMPOSE_PROFILES` en `.env` decide qué levanta cada casa
  (`face` = Hailo/cámara, `obs` = monitor). Casa principal: `face,obs`.
- **Casa nueva**: ver `docs/runbooks/onboarding-casa-nueva.md`.
```

- [ ] **Step 2: `docs/estado-actual.md`** — agregar bajo "Accesos y secretos":
```markdown
- `homeassistant/secrets.yaml` (fuera de git): `st_bearer`, `st_url`, `lg_mac`, `samsung_mac`.
  Plantilla en `secrets.yaml.example`. Los packages los usan con `!secret`.
- `COMPOSE_PROFILES` en `.env` (casa principal: `face,obs`).
```

- [ ] **Step 3: `docs/runbooks/pendientes.md`** — cerrar el refactor de arquitectura:
```markdown
- HECHO 2026-09-28: **Parametrización** — MACs/URL ST a `secrets.yaml` (+ `secrets.yaml.example`),
  compose profiles (face/obs), doc `onboarding-casa-nueva.md`. **Refactor de arquitectura COMPLETO
  (los 3 sub-proyectos).** entity_ids/IDs Tizen/grilla se cubren por convención + onboarding.
```

- [ ] **Step 4: `docs/runbooks/instalacion-r2130.md`** — en el paso de recovery de secretos, referenciar:
```markdown
- Para una casa NUEVA (no recovery), seguir `onboarding-casa-nueva.md`.
- `secrets.yaml`: completar desde `secrets.yaml.example` (st_bearer, st_url, lg_mac, samsung_mac).
```

- [ ] **Step 5: Commit**

```bash
git add README.md docs/estado-actual.md docs/runbooks/pendientes.md docs/runbooks/instalacion-r2130.md
git commit -m "docs: parametrización — secrets/profiles/onboarding en README y runbooks"
git push
```

---

### Task 5: Verificación final del refactor completo

**Files:** ninguno.

- [ ] **Step 1: Runtime idéntico**

```bash
checkcfg
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
d=json.load(sys.stdin)
for pref in ("automation.","script.","switch.","binary_sensor.salud"):
    print(pref, sum(1 for e in d if e["entity_id"].startswith(pref)))'
```
Expected: `check_config` sin ERROR; conteos = 19 automation, 13 script, 6 switch, 3 salud (igual que antes).

- [ ] **Step 2: Prueba funcional de un `!secret`**

```bash
# lanzar una app del Samsung (usa st_url desde secret)
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"script.netflix_dormitorio"}' $BASE/services/script/turn_on >/dev/null && echo "netflix_dormitorio disparado"
```
Expected: si el Samsung está encendido, abre Netflix (confirma que `st_url` desde secret funciona). Si está apagado, el script intenta WoL primero (usa `samsung_mac` desde secret).

- [ ] **Step 3: `docker compose config` con y sin profiles**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation
echo "=== con face,obs (casa principal) ==="; COMPOSE_PROFILES=face,obs docker compose config --services | sort
echo "=== sin profiles (casa base) ==="; COMPOSE_PROFILES= docker compose config --services | sort
EOF
```
Expected: con `face,obs` → 6 servicios; sin profiles → solo `mosquitto`, `homeassistant`, `cloudflared-mcp` (la base).

---

## Self-review (cobertura de la spec)

- Capa 1 (secrets `lg_mac`/`samsung_mac`/`st_url` + `secrets.yaml.example` + `!secret` en tv.yaml) → **Task 1** ✓
- Capa 2 (entity_ids/IDs Tizen/grilla por convención + doc) → **Task 3** (onboarding lo documenta) ✓
- Capa 3 (compose profiles face/obs + `COMPOSE_PROFILES` en .env + .env.example) → **Task 2** ✓
- Doc de onboarding (entregable estrella) → **Task 3** ✓
- Documentación MUST (README, estado-actual, pendientes, instalacion) → **Task 4** ✓
- Runtime idéntico (secrets resuelven a valores actuales; profiles activos en casa principal) → **Task 1 Step 5, Task 5** ✓
- Cierre del refactor de arquitectura (3 sub-proyectos) → **Task 4 Step 3** ✓
- Nota: `secrets.yaml` real se edita en la R2130 (fuera de git); solo `secrets.yaml.example` va al repo.
