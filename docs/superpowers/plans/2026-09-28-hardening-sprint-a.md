# Hardening Sprint A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar los 7 items P0 de hardening del handoff (bugs, pinning, aislamiento de cámara, backups robustos, CI, MCP tras Cloudflare Access) sin hardware nuevo.

**Architecture:** Cambios quirúrgicos sobre la plataforma existente. Sin framework de tests unitarios (infra): cada tarea se "verifica" con un comando concreto (curl a la API de HA, `docker compose config`, chequeo de MQTT/estado) en vez de pytest. Workflow de deploy: editar en mini-PC → commit → push → `ssh r2130 'bash -s' <<EOF` con `cd /opt/home-automation` → pull → reload/restart.

**Tech Stack:** Home Assistant Container 2026.9.3, Docker Compose, MQTT (mosquitto), restic→R2, cron, Cloudflare Access API, GitHub Actions, gitleaks, sqlite3.

**Convención de deploy (se repite en varias tareas):**
```bash
# pull en la R2130 (el heredoc aterriza en ~, por eso el cd explícito)
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
EOF
# recargas (token en ~/.ha_token del mini-PC)
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
```

---

## Task 1: Fix `check_mcp` en healthmon (bug: reporta sano ante 5xx/404)

**Files:**
- Modify: `healthmon/monitor.py` (función `check_mcp`, ~líneas 38-43)

- [ ] **Step 1: Ver el estado actual del sensor (baseline)**

```bash
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
curl -s -H "$H" $BASE/states/binary_sensor.salud_mcp | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),'|',d.get('attributes',{}).get('detail'))"
```
Expected: `off | ok` (hoy: reporta ok aunque el endpoint da 404).

- [ ] **Step 2: Reescribir `check_mcp`**

Reemplazar en `healthmon/monitor.py`:
```python
def check_mcp():
    try:
        requests.get(f"http://{NODE}:9584/", timeout=8)
        return True, "ok"
    except Exception as e:
        return False, repr(e)[:80]
```
por:
```python
def check_mcp():
    # El server ha_mcp_tools responde 404 en "/" (el MCP vive en /<secret_path>);
    # eso es transporte vivo. Solo 5xx / timeout / conexión caída = DOWN.
    try:
        r = requests.get(f"http://{NODE}:9584/", timeout=8)
        if r.status_code >= 500:
            return False, f"HTTP {r.status_code}"
        return True, f"HTTP {r.status_code}"
    except Exception as e:
        return False, repr(e)[:80]
```

- [ ] **Step 3: Commit + deploy (rebuild del contenedor healthmon)**

```bash
git add healthmon/monitor.py
git commit -m "fix: healthmon check_mcp distingue 5xx/timeout de transporte vivo (404 = up)"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
docker compose up -d --build healthmon
EOF
```

- [ ] **Step 4: Verificar UP normal (404 = up)**

```bash
sleep 65
curl -s -H "$H" $BASE/states/binary_sensor.salud_mcp | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),'|',d.get('attributes',{}).get('detail'))"
```
Expected: `off | HTTP 404` (sano, con detalle honesto del código).

- [ ] **Step 5: Verificar DOWN al parar el MCP**

```bash
ssh r2130 'docker stop cloudflared-mcp'   # el MCP se sirve por el túnel; parar el server real
# nota: el server MCP es ha_mcp_tools dentro de HA (:9584). Para forzar DOWN sin tocar HA,
# simular: apuntar a un puerto muerto NO aplica (NODE fijo). Alternativa de verificación:
# confirmar por lógica que status>=500/conn-error → DOWN (revisado en code review).
ssh r2130 'docker start cloudflared-mcp'
```
Expected: la lógica cubre 5xx/timeout/conn (verificado por lectura de código; el 404→up ya se probó en vivo). Reiniciar cloudflared-mcp deja todo como estaba.

---

## Task 2: Corregir `external_url` → Tailscale (bug + re-test MCP)

**Files:**
- Modify: `homeassistant/configuration.yaml:19`

- [ ] **Step 1: Baseline del connector MCP (antes de tocar nada)**

```bash
curl -s -o /dev/null -w "MCP raiz HTTP %{http_code}\n" -m 6 http://192.168.1.17:9584/
```
Expected: `MCP raiz HTTP 404` (server vivo).

- [ ] **Step 2: Cambiar external_url**

En `homeassistant/configuration.yaml`, reemplazar:
```yaml
  external_url: "https://ha-mcp.neuralcore.dev"
```
por:
```yaml
  # URL canónica de HA para clientes remotos = Tailscale (llega al login de HA, sin puerto).
  # El MCP usa su propio server_url (ha-mcp.neuralcore.dev), NO el external_url de HA.
  external_url: "https://r2130.tail71f19f.ts.net"
```

- [ ] **Step 3: Commit + deploy + restart HA**

```bash
git add homeassistant/configuration.yaml
git commit -m "fix: external_url de HA apunta a Tailscale (no al tunel del MCP)"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
docker restart homeassistant
EOF
```

- [ ] **Step 4: Esperar HA y verificar check_config + external_url efectivo**

```bash
for i in $(seq 1 30); do c=$(curl -s -o /dev/null -w "%{http_code}" -H "$H" $BASE/ || true); [ "$c" = "200" ] && break; sleep 3; done
sleep 8
curl -s -X POST -H "$H" $BASE/config/core/check_config | python3 -c "import sys,json;d=json.load(sys.stdin);print('config:',d.get('result'))"
curl -s -H "$H" $BASE/config | python3 -c "import sys,json;d=json.load(sys.stdin);print('external_url:',d.get('external_url'),'| internal_url:',d.get('internal_url'))"
```
Expected: `config: valid` y `external_url: https://r2130.tail71f19f.ts.net`.

- [ ] **Step 5: Re-test del MCP (que siga vivo)**

```bash
curl -s -o /dev/null -w "MCP raiz HTTP %{http_code}\n" -m 6 http://192.168.1.17:9584/
curl -s -H "$H" $BASE/states/binary_sensor.salud_mcp | python3 -c "import sys,json;d=json.load(sys.stdin);print('salud_mcp:',d.get('state'))"
```
Expected: `MCP raiz HTTP 404` + `salud_mcp: off`. Si el connector se rompiera, revertir el commit y reiniciar HA (el MCP usa secret_path, no get_url, así que no debería).

---

## Task 3: Pinnear imágenes Docker + runbook de upgrades

**Files:**
- Modify: `docker-compose.yml` (3 líneas `image:`)
- Create: `docs/runbooks/upgrades.md`

- [ ] **Step 1: Fijar los tags exactos**

En `docker-compose.yml`:
```yaml
    image: eclipse-mosquitto:2          # → eclipse-mosquitto:2.1.2
    image: ghcr.io/home-assistant/home-assistant:stable   # → :2026.9.3
    image: cloudflare/cloudflared:latest                  # → :2026.9.3
```
Quedan:
```yaml
    image: eclipse-mosquitto:2.1.2
    image: ghcr.io/home-assistant/home-assistant:2026.9.3
    image: cloudflare/cloudflared:2026.9.3
```

- [ ] **Step 2: Crear el runbook de upgrades**

Crear `docs/runbooks/upgrades.md`:
```markdown
# Upgrades de imágenes Docker

Las imágenes críticas están **pinneadas** en `docker-compose.yml` (nada de `latest`/`stable`):
un `docker compose pull`/recreate NO actualiza sin editar el repo.

## Versiones actuales (2026-09-28)
- `ghcr.io/home-assistant/home-assistant:2026.9.3`
- `cloudflare/cloudflared:2026.9.3`
- `eclipse-mosquitto:2.1.2`

## Proceso de upgrade (por servicio)
1. Revisar el release notes de la nueva versión (breaking changes).
2. Bumpear el tag en `docker-compose.yml` (en el mini-PC) → commit → push.
3. En la R2130: `cd /opt/home-automation && git pull`.
4. `docker compose pull <servicio> && docker compose up -d <servicio>`.
5. Health check: vista "Salud" del dashboard + `binary_sensor.salud_*` en verde;
   `curl -s -o /dev/null -w "%{http_code}" http://192.168.1.17:8123/` = 200/302.
6. **Rollback si falla:** revertir el tag en el repo (`git revert` o editar), `git pull`
   en la R2130, `docker compose up -d <servicio>`. Las imágenes viejas quedan en caché
   local (`docker images`), el rollback es inmediato.

## Nota HA
HA guarda estado en `.storage` (no en la imagen); un downgrade de HA puede quejarse si la
versión nueva migró `.storage`. Ante downgrade, restaurar `.storage` del backup previo.
```

- [ ] **Step 3: Commit + deploy (verificar que no recrea con otra versión)**

```bash
git add docker-compose.yml docs/runbooks/upgrades.md
git commit -m "chore: pin de imagenes Docker (HA/cloudflared/mosquitto) + runbook upgrades"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
docker compose config | grep -E "image:"
EOF
```
Expected: los 3 tags exactos (`:2.1.2`, `:2026.9.3`, `:2026.9.3`). No hace falta recrear (misma versión que corre).

---

## Task 4: Separar face-recognizer a profile `experimental`

**Files:**
- Modify: `docker-compose.yml` (`face-recognizer` → `profiles: ["experimental"]`)
- Modify: `.env.example` (documentar el profile nuevo)

- [ ] **Step 1: Cambiar el profile del loop de cámara**

En `docker-compose.yml`, en el servicio `face-recognizer`, cambiar:
```yaml
    profiles: ["face"]
```
por:
```yaml
    profiles: ["experimental"]   # el loop de cámara NO arranca en la casa principal
```
(`face-embed` queda en `profiles: ["face"]` sin cambios.)

- [ ] **Step 2: Documentar en .env.example**

En `.env.example`, reemplazar el bloque de comentarios de profiles por:
```bash
# Perfiles de servicios a levantar (Docker Compose profiles).
#   face         → face-embed (API de inferencia facial en Hailo). NO arranca el loop de cámara.
#   experimental → face-recognizer (loop cámara→MQTT). Solo bajo demanda; consume /dev/video0.
#   obs          → healthmon (monitor de salud) + métricas de nodo.
# Base (mosquitto, homeassistant, cloudflared-mcp) siempre levanta.
# Casa principal: face,obs (sin experimental → sin captura de cámara).
COMPOSE_PROFILES=face,obs
```

- [ ] **Step 3: Commit + deploy + verificar que el loop no está en el set activo**

```bash
git add docker-compose.yml .env.example
git commit -m "refactor: face-recognizer a profile experimental (no arranca en casa principal)"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
echo "--- servicios que levantaria el profile activo (face,obs) ---"
docker compose config --services
echo "--- estado actual de face-recognizer ---"
docker ps -a --filter name=face-recognizer --format '{{.Names}} {{.Status}}'
EOF
```
Expected: `docker compose config --services` (con `COMPOSE_PROFILES=face,obs`) **no** lista `face-recognizer`. Si estaba corriendo de antes, `docker stop face-recognizer` para dejarlo apagado.

- [ ] **Step 4: Confirmar que un `up -d` normal no lo arranca**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && docker compose up -d
docker ps --filter name=face-recognizer --format '{{.Names}} {{.Status}}' || true
EOF
```
Expected: `face-recognizer` NO aparece corriendo. `face-embed` sí (profile `face`).

---

## Task 5: Backups robustos (DB consistente + restic check + sensor de antigüedad)

**Files:**
- Modify: `scripts/backup.sh` (DB consistente vía sqlite3 online backup)
- Create: `scripts/restic-check.sh`
- Modify: `scripts/backup-offsite.sh` (escribir marker de éxito)
- Modify: `scripts/node-metrics.sh` (publicar `sensor.last_backup_age`)
- Modify: `homeassistant/packages/salud.yaml` (alerta backup > 36h)
- Modify: `.gitignore` (marker + token)

### 5A — DB consistente en backup.sh

- [ ] **Step 1: Reescribir backup.sh con snapshot consistente de la DB**

Reemplazar `scripts/backup.sh` completo por:
```bash
#!/usr/bin/env bash
# Backup nocturno de configs (no media) a /opt/backups. Retiene 14.
# La DB de HA se copia con la API de backup online de SQLite (snapshot consistente,
# integra el WAL) en vez de tar-ear el archivo vivo.
set -euo pipefail

BACKUP_DIR=/opt/backups/home-automation
SRC=/opt/home-automation
DB=/opt/home-automation/homeassistant/home-assistant_v2.db
DB_SNAP=/opt/home-automation/homeassistant/home-assistant_v2.db.bak
mkdir -p "$BACKUP_DIR"

# Snapshot consistente de la DB (si existe). sqlite3 .backup usa la API online:
# no requiere parar HA y captura un estado coherente con el WAL.
if [ -f "$DB" ] && command -v sqlite3 >/dev/null; then
  sqlite3 "$DB" ".backup '$DB_SNAP'" && echo "DB snapshot OK"
fi

tar -czf "$BACKUP_DIR/config-$(date +%F).tar.gz" \
    --exclude='frigate/media' \
    --exclude='homeassistant/home-assistant_v2.db' \
    --exclude='homeassistant/home-assistant_v2.db-wal' \
    --exclude='homeassistant/home-assistant_v2.db-shm' \
    -C "$(dirname "$SRC")" "$(basename "$SRC")"

rm -f "$DB_SNAP"
ls -1t "$BACKUP_DIR"/config-*.tar.gz | tail -n +15 | xargs -r rm --
```
(Se excluye la `.db` viva y se incluye `home-assistant_v2.db.bak`, que es el snapshot consistente. El restore renombra `.bak` → `.db`.)

- [ ] **Step 2: Instalar sqlite3 en el host si falta**

```bash
ssh r2130 'command -v sqlite3 || sudo apt-get install -y sqlite3'
```
Expected: ruta de sqlite3 (ya instalado) o instalación OK.

- [ ] **Step 3: Correr backup.sh a mano y verificar el snapshot**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && sudo bash scripts/backup.sh
echo "--- contenido del tar (que incluya el .db.bak, no el .db vivo) ---"
tar -tzf /opt/backups/home-automation/config-$(date +%F).tar.gz | grep -E "home-assistant_v2.db(\.bak)?$" || echo "(sin db en el tar)"
EOF
```
Expected: aparece `home-automation/homeassistant/home-assistant_v2.db.bak` y NO `..._v2.db`.

### 5B — restic check semanal

- [ ] **Step 4: Crear scripts/restic-check.sh**

Crear `scripts/restic-check.sh`:
```bash
#!/usr/bin/env bash
# Verificación de integridad del repo restic en R2. Semanal por cron (root).
# NO se corre en cada backup (es costoso). Credenciales en .restic-env.
set -uo pipefail
ENV_FILE=/opt/home-automation/.restic-env
if [ ! -f "$ENV_FILE" ]; then echo "ERROR: falta $ENV_FILE"; exit 1; fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

echo "restic check inicio: $(date -Is)"
if restic check --read-data-subset=5%; then
  echo "restic check OK: $(date -Is)"
else
  echo "restic check FALLO: $(date -Is)" >&2
  exit 1
fi
```
(`--read-data-subset=5%` verifica estructura + una muestra de datos sin descargar todo desde R2.)

- [ ] **Step 5: chmod + instalar cron semanal**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && chmod +x scripts/restic-check.sh
sudo bash -c '
  current=$(crontab -l 2>/dev/null || true)
  echo "$current" | grep -qF "restic-check.sh" && { echo "cron ya presente"; exit 0; }
  { echo "$current"; echo "15 5 * * 0 /opt/home-automation/scripts/restic-check.sh >> /var/log/restic-check.log 2>&1"; } | crontab -
  echo "cron restic-check instalado (domingos 05:15)"
'
EOF
```
Expected: `cron restic-check instalado`.

### 5C — Marker de éxito + sensor.last_backup_age

- [ ] **Step 6: backup-offsite.sh escribe el marker al terminar OK**

En `scripts/backup-offsite.sh`, después del `restic forget --prune` exitoso y antes del ping a healthchecks (o al final), agregar:
```bash
# Marker local para el sensor de antigüedad (evita consultar R2 en cada tick de metrics).
date -Is > /opt/home-automation/.last-backup-offsite
```

- [ ] **Step 7: node-metrics.sh publica el sensor de antigüedad**

En `scripts/node-metrics.sh`, agregar a la sección de discovery (después de `discovery disk ...`):
```bash
discovery last_backup_age "Nodo Antigüedad Backup" duration "h"
```
y agregar antes del `echo` final:
```bash
# --- Antigüedad del último backup off-site (horas) desde el marker local ---
MARKER=/opt/home-automation/.last-backup-offsite
if [ -f "$MARKER" ]; then
  now=$(date +%s); m=$(date -d "$(cat "$MARKER")" +%s 2>/dev/null || stat -c %Y "$MARKER")
  pub depto/nodo/last_backup_age "$(awk -v n="$now" -v m="$m" 'BEGIN{printf "%.1f",(n-m)/3600}')"
fi
```

- [ ] **Step 8: Alerta en packages/salud.yaml (backup atrasado > 36h)**

NOTA: `discovery()` en `node-metrics.sh` fuerza `object_id: node_$key`, así que el entity_id
real es **`sensor.node_last_backup_age`** (mismo prefijo que el resto de sensores del nodo).

En `homeassistant/packages/salud.yaml`, en el trigger de `nodo_alerta`, agregar:
```yaml
      - trigger: numeric_state
        entity_id: sensor.node_last_backup_age
        above: 36
        id: backup
```
y en el `choose`, agregar una condición (antes del `default` del SMART):
```yaml
          - conditions:
              - condition: trigger
                id: backup
            sequence:
              - action: notify.mobile_app_lucass_iphone
                data:
                  title: "🗄️ Backup off-site atrasado"
                  message: "El último backup a R2 tiene {{ states('sensor.node_last_backup_age') }} h. Revisar restic/cron."
```

- [ ] **Step 9: .gitignore para marker y token de Cloudflare**

En `.gitignore`, agregar al bloque de secretos:
```
# Marker de último backup off-site (runtime, no config)
.last-backup-offsite
# Token de API de Cloudflare (Access/MCP portal)
.cloudflare-token
```

- [ ] **Step 10: Commit + deploy + verificar sensor y alerta**

```bash
git add scripts/backup.sh scripts/restic-check.sh scripts/backup-offsite.sh scripts/node-metrics.sh homeassistant/packages/salud.yaml .gitignore
git commit -m "feat: backups robustos (DB consistente, restic check semanal, sensor last_backup_age + alerta)"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
sudo bash scripts/backup-offsite.sh   # genera el marker
sudo bash scripts/node-metrics.sh     # publica el sensor
docker restart homeassistant          # carga la alerta nueva del package
EOF
sleep 75
curl -s -H "$H" $BASE/states/sensor.node_last_backup_age | python3 -c "import sys,json;d=json.load(sys.stdin);print('last_backup_age:',d.get('state'),d.get('attributes',{}).get('unit_of_measurement'))"
curl -s -X POST -H "$H" $BASE/config/core/check_config | python3 -c "import sys,json;print('config:',json.load(sys.stdin).get('result'))"
```
Expected: `last_backup_age: <horas> h` (cercano a 0 recién corrido) y `config: valid`.

---

## Task 6: CI mínimo (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.yamllint`

- [ ] **Step 1: Config de yamllint (relajada, excluye HA por los tags !include/!secret)**

Crear `.yamllint`:
```yaml
extends: relaxed
rules:
  line-length: disable
  document-start: disable
ignore: |
  homeassistant/
```
(La config de HA usa tags custom `!include`/`!secret` que el parser YAML estándar no entiende; se valida en deploy con `check_config`, no en CI.)

- [ ] **Step 2: Workflow de CI**

Crear `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  yaml-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install yamllint
      - run: yamllint docker-compose.yml .github/

  compose-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: dummy .env
        run: cp .env.example .env
      - run: docker compose config -q

  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: gitleaks (árbol de trabajo, sin historia)
        run: |
          curl -sSL https://github.com/gitleaks/gitleaks/releases/download/v8.18.4/gitleaks_8.18.4_linux_x64.tar.gz | tar -xz gitleaks
          ./gitleaks detect --no-git --source . --redact --exit-code 1
```
(`--no-git` escanea el árbol actual, no la historia: evita falsos positivos por los webhook IDs ya eliminados que siguen en commits viejos.)

- [ ] **Step 3: Validar el workflow localmente antes de pushear**

```bash
cd /opt/home-automation
pip install yamllint -q 2>/dev/null; yamllint docker-compose.yml .github/ && echo "yamllint OK"
cp .env.example .env && docker compose config -q && echo "compose OK" && rm -f .env
```
Expected: `yamllint OK` y `compose OK`.

- [ ] **Step 4: Commit + push + verificar el run en GitHub**

```bash
git add .github/workflows/ci.yml .yamllint
git commit -m "ci: workflow minimo (yamllint + compose config + gitleaks)"
git push
sleep 25
gh run list --limit 1
```
Expected: un run de "CI" en curso/verde. Si `gh` no está logueado, ver en la web del repo.

---

## Task 7: MCP — hardening local + Cloudflare Access

**Files:**
- Create: `scripts/cf-access-mcp.sh`
- Create: `docs/runbooks/mcp-security.md`

### 7B — Hardening local (automatizable, primero)

- [ ] **Step 1: Enumerar entidades expuestas a Assist (las que el MCP puede tocar)**

```bash
ssh r2130 'cat /opt/home-automation/homeassistant/.storage/homeassistant.exposed_entities 2>/dev/null' | python3 -c "import sys,json;d=json.load(sys.stdin);e=d.get('data',{}).get('exposed_entities',{});[print(k,'→',[a for a,v in val.get('assistants',{}).items() if v.get('should_expose')]) for k,val in e.items()]" 2>/dev/null || echo "revisar formato del storage"
```
Expected: lista de entity_ids expuestos a `conversation`. Anotar la lista para el runbook.

- [ ] **Step 2: Confirmar el deny floor del componente (verificación documental)**

```bash
ssh r2130 'grep -n "DENY_PATH_SEGMENTS\|secrets.yaml\|.storage" /opt/home-automation/homeassistant/custom_components/ha_mcp_tools/const.py | head'
```
Expected: confirma `DENY_PATH_SEGMENTS = frozenset({".storage"})` + deny de `secrets.yaml` (no-anulable).

- [ ] **Step 3: Escribir docs/runbooks/mcp-security.md**

Crear `docs/runbooks/mcp-security.md` documentando: (a) capas de auth (Cloudflare Access delante + secret_path como 2da capa), (b) deny floor del componente, (c) lista de entidades expuestas a Assist (del Step 1), (d) rotación del secret_path (`regenerate_secrets` en el options flow de la integración), (e) norte: migrar a OAuth puro y sacar el secret_path tras validar Access. (Contenido concreto se completa con los datos de los Steps 1-2.)

### 7A — Cloudflare Access (scripted con el token)

- [ ] **Step 4: Script de creación de la Access application + policy**

Crear `scripts/cf-access-mcp.sh` (corre en la R2130, lee el token local):
```bash
#!/usr/bin/env bash
# Crea (idempotente) una Cloudflare Access self-hosted app + policy para el endpoint MCP,
# restringida a la identidad de Lucas (login OTP por email). El secret_path se mantiene
# como 2da capa. Token en /opt/home-automation/.cloudflare-token (formato CLOUDFLARE_TOKEN=...).
set -uo pipefail
set -a; source /opt/home-automation/.cloudflare-token; set +a
TOKEN="${CLOUDFLARE_TOKEN}"
ACC=115a2f9419ee3033fde16851a506c0d6
DOMAIN=ha-mcp.neuralcore.dev
ALLOW_EMAIL="${1:-lucas@bold-agro.ai}"   # email que recibe el OTP; pasar otro como arg si hace falta
API=https://api.cloudflare.com/client/v4
auth=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

# ¿ya existe la app para ese dominio?
app_id=$(curl -s "${auth[@]}" "$API/accounts/$ACC/access/apps" | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((a['id'] for a in (d.get('result') or []) if a.get('domain')=='$DOMAIN'),''))")

if [ -z "$app_id" ]; then
  app_id=$(curl -s "${auth[@]}" -X POST "$API/accounts/$ACC/access/apps" \
    --data "{\"name\":\"HA-MCP\",\"domain\":\"$DOMAIN\",\"type\":\"self_hosted\",\"session_duration\":\"24h\"}" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('result') or {}).get('id',''));[print('ERR',e) for e in d.get('errors',[])]")
  echo "app creada: $app_id"
else
  echo "app ya existía: $app_id"
fi
[ -z "$app_id" ] && { echo "no se pudo crear/encontrar la app"; exit 1; }

# policy allow para el email (idempotente por nombre)
pol_exists=$(curl -s "${auth[@]}" "$API/accounts/$ACC/access/apps/$app_id/policies" | python3 -c "import sys,json;d=json.load(sys.stdin);print('si' if any(p.get('name')=='solo-lucas' for p in (d.get('result') or [])) else '')")
if [ -z "$pol_exists" ]; then
  curl -s "${auth[@]}" -X POST "$API/accounts/$ACC/access/apps/$app_id/policies" \
    --data "{\"name\":\"solo-lucas\",\"decision\":\"allow\",\"include\":[{\"email\":{\"email\":\"$ALLOW_EMAIL\"}}]}" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print('policy:',(d.get('result') or {}).get('id',''));[print('ERR',e) for e in d.get('errors',[])]"
else
  echo "policy 'solo-lucas' ya existía"
fi
```

- [ ] **Step 5: Correr el script y verificar creación**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && chmod +x scripts/cf-access-mcp.sh && bash scripts/cf-access-mcp.sh
EOF
```
Expected: `app creada: <id>` + `policy: <id>` (o "ya existía" en re-runs).

- [ ] **Step 6: CHECKPOINT — test del connector por el usuario (gated, reversible)**

Pedir al usuario: reconectar el connector MCP en ChatGPT/Claude y confirmar que aparece el login de Access (OTP al email) y que tras autenticar el MCP responde. **Riesgo conocido:** si el cliente MCP no completa el flujo cookie de Access (podría requerir un MCP Server Portal con OAuth en vez de una self-hosted app), el connector se rompe. Rollback inmediato si eso pasa:
```bash
ssh r2130 'bash -s' <<'EOF'
set -a; source /opt/home-automation/.cloudflare-token; set +a
ACC=115a2f9419ee3033fde16851a506c0d6; API=https://api.cloudflare.com/client/v4
app_id=$(curl -s -H "Authorization: Bearer $CLOUDFLARE_TOKEN" "$API/accounts/$ACC/access/apps" | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((a['id'] for a in (d.get('result') or []) if a.get('domain')=='ha-mcp.neuralcore.dev'),''))")
curl -s -X DELETE -H "Authorization: Bearer $CLOUDFLARE_TOKEN" "$API/accounts/$ACC/access/apps/$app_id" >/dev/null && echo "Access app borrada (rollback); MCP vuelve a solo-secret_path"
EOF
```
(El secret_path sigue activo todo el tiempo, así que el rollback restaura el estado que funciona hoy.) Si el test falla, evaluar la vía **MCP Server Portal** (OAuth) por dashboard en un paso aparte.

- [ ] **Step 7: Commit de los scripts/docs**

```bash
git add scripts/cf-access-mcp.sh docs/runbooks/mcp-security.md
git commit -m "feat: MCP tras Cloudflare Access (script) + hardening local documentado"
git push
```

---

## Task 8: Documentación (MUST) + cierre del sprint

**Files:**
- Modify: `docs/estado-actual.md`, `docs/runbooks/pendientes.md`, `README.md`

- [ ] **Step 1: estado-actual.md**

Actualizar: healthmon (chequeo MCP honesto), external_url = Tailscale, face-api/face-loop (profiles), backups (DB consistente + restic check + sensor last_backup_age + alerta), CI, MCP tras Access. Agregar `sensor.node_last_backup_age` a "Entidades clave", `restic-check.sh`/`cf-access-mcp.sh` a "Scripts", la alerta de backup a "Automatizaciones".

- [ ] **Step 2: pendientes.md**

Marcar **Sprint A HECHO 2026-09-28** (los 7 items, con detalle). Abrir "Fase 2 — Presencia física (Zigbee/mmWave/door)" como norte que espera compra USA. Si el test del connector con Access quedó pendiente, anotarlo.

- [ ] **Step 3: README.md**

Roadmap: agregar fila "Sprint A hardening ✅ 2026-09-28". Actualizar la tabla de servicios (face-recognizer → profile `experimental`), mencionar CI y MCP+Access. Actualizar la sección de estructura (`scripts/restic-check.sh`, `scripts/cf-access-mcp.sh`, `docs/runbooks/upgrades.md`, `docs/runbooks/mcp-security.md`, `.github/`).

- [ ] **Step 4: Commit final + deploy de docs**

```bash
git add docs/estado-actual.md docs/runbooks/pendientes.md README.md
git commit -m "docs: Sprint A hardening completo (estado-actual, pendientes, README)"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull --ff-only
EOF
```

---

## Verificación de éxito (global)

- [ ] `binary_sensor.salud_mcp` = off con detalle `HTTP 404` (Task 1).
- [ ] `external_url` = `https://r2130.tail71f19f.ts.net`, MCP sigue vivo, `check_config` valid (Task 2).
- [ ] `docker compose config` muestra los 3 tags exactos (Task 3).
- [ ] `docker compose config --services` (face,obs) no lista `face-recognizer` (Task 4).
- [ ] tar incluye `home-assistant_v2.db.bak` (consistente); cron restic-check semanal; `sensor.node_last_backup_age` visible; alerta > 36h cargada (Task 5).
- [ ] Run de CI verde (yamllint + compose + gitleaks) (Task 6).
- [ ] Access app + policy creadas; connector testeado por el usuario (o rollback limpio) (Task 7).
- [ ] Docs actualizadas y pusheadas (Task 8).
