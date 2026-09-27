# Backup off-site cifrado (restic → R2) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copia cifrada e incremental de `/opt/home-automation` en Cloudflare R2 con restic, cron diario, retención y restore test. Según `docs/superpowers/specs/2026-09-28-backup-offsite-design.md`.

**Architecture:** `restic` (backend s3 → R2) corre en el host por cron (~04:45, tras el backup local). Credenciales + password de repo en `/opt/home-automation/.restic-env` (fuera de git). Al terminar OK pinguea un dead-man (healthchecks.io).

**Tech Stack:** restic, Cloudflare R2 (S3-compatible), bash, cron.

**Prerrequisito del usuario:** crear bucket R2 + API token y pasar `account_id`, `access_key_id`, `secret_access_key`, `bucket`, y elegir una `RESTIC_PASSWORD` (guardada fuera del R2130). Sin esto, el script se instala pero no puede correr contra R2.

```bash
# host de trabajo: mini-PC; deploy vía git pull en la R2130 (ssh r2130)
```

---

### Task 1: `.restic-env.example` + `.gitignore`

**Files:**
- Create: `.restic-env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Crear `.restic-env.example`** (versionado, sin valores reales)

```sh
# Copiar a .restic-env (fuera de git, chmod 600) en la R2130 y completar.
# Repo restic sobre Cloudflare R2 (S3-compatible):
export RESTIC_REPOSITORY="s3:https://<account_id>.r2.cloudflarestorage.com/<bucket>"
export AWS_ACCESS_KEY_ID="<r2_access_key_id>"
export AWS_SECRET_ACCESS_KEY="<r2_secret_access_key>"
# Password del repo restic — CRÍTICA: guardarla también FUERA del R2130 (gestor de contraseñas).
# Sin esta password NO se puede restaurar el backup.
export RESTIC_PASSWORD="<password-repo-restic>"
# Dead-man switch del backup (healthchecks.io) — opcional:
export BACKUP_HC_URL=""
```

- [ ] **Step 2: Ignorar `.restic-env` en git**

En `.gitignore`, en la sección de secretos, agregar:
```
# Credenciales del backup off-site (restic + R2)
.restic-env
```

- [ ] **Step 3: Commit**

```bash
git add .restic-env.example .gitignore
git commit -m "feat: plantilla .restic-env para backup off-site (restic/R2)"
git push
```

---

### Task 2: Script `scripts/backup-offsite.sh`

**Files:**
- Create: `scripts/backup-offsite.sh`

- [ ] **Step 1: Escribir `scripts/backup-offsite.sh`**

```bash
#!/usr/bin/env bash
# Backup off-site cifrado a Cloudflare R2 con restic.
# Corre en el host por cron, después del backup local. Credenciales en .restic-env (fuera de git).
set -euo pipefail

ENV_FILE=/opt/home-automation/.restic-env
SRC=/opt/home-automation

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: falta $ENV_FILE (credenciales R2 + password restic)"; exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

# Inicializar el repo la primera vez (si aún no existe).
if ! restic snapshots >/dev/null 2>&1; then
  echo "Inicializando repo restic en R2..."
  restic init
fi

# Backup incremental cifrado.
restic backup "$SRC" \
  --tag r2130 \
  --exclude "$SRC/frigate/media" \
  --exclude "**/__pycache__" \
  --exclude "*.log" \
  --exclude "*.log.*" \
  --exclude "$SRC/homeassistant/home-assistant_v2.db-wal" \
  --exclude "$SRC/homeassistant/home-assistant_v2.db-shm"

# Retención.
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

# Dead-man switch: solo si todo lo anterior salió OK (set -e aborta antes si falla).
if [ -n "${BACKUP_HC_URL:-}" ]; then
  curl -fsS -m 15 "$BACKUP_HC_URL" >/dev/null || echo "aviso: ping a healthchecks falló"
fi

echo "backup off-site OK: $(date -Is)"
```

Nota: el script respalda `/opt/home-automation` completo (que incluye `.env`, `secrets.yaml`,
`.storage`, `custom_components`, `cloudflared/*.json`, `face-embed/data`, etc.); `/opt/backups`
(tar local) está fuera de `$SRC`, no se incluye.

- [ ] **Step 2: Permisos y commit**

```bash
chmod +x scripts/backup-offsite.sh
git add scripts/backup-offsite.sh
git commit -m "feat: script backup-offsite (restic → R2, retención, dead-man)"
git push
```

---

### Task 3: Instalar restic + credenciales en la R2130

**Files:** ninguno en git (setup del host).

- [ ] **Step 1: Instalar restic en la R2130**

```bash
ssh r2130 'command -v restic >/dev/null && restic version || (sudo apt-get update -qq && sudo apt-get install -y restic && restic version)'
```
Expected: imprime la versión de restic (≥ 0.16).

- [ ] **Step 2: Crear `.restic-env` con los valores del usuario**

El usuario provee `account_id`, `bucket`, `access_key_id`, `secret_access_key`, `RESTIC_PASSWORD`.
Crear el archivo en la R2130 (fuera de git):
```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation
cp -n .restic-env.example .restic-env
chmod 600 .restic-env
echo "editar /opt/home-automation/.restic-env con los valores reales de R2"
EOF
```
Luego completar los valores (con los datos del usuario). Verificar que quedó 600 y con las 4
variables + repo.

- [ ] **Step 3: Verificar conexión a R2 (init del repo)**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation
source .restic-env
restic snapshots >/dev/null 2>&1 || restic init
restic snapshots
EOF
```
Expected: `restic init` crea el repo en R2 (primera vez) y `restic snapshots` lista (vacío o con snapshots). Si da error de credenciales/endpoint, revisar `.restic-env`.

---

### Task 4: Primera corrida + verificación (restore test)

**Files:** ninguno.

- [ ] **Step 1: Correr el backup manualmente**

```bash
ssh r2130 '/opt/home-automation/scripts/backup-offsite.sh'
```
Expected: termina con `backup off-site OK: <fecha>`; sin errores.

- [ ] **Step 2: Verificar el snapshot y la integridad**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && source .restic-env
echo "=== snapshots ==="; restic snapshots
echo "=== check ==="; restic check
EOF
```
Expected: al menos 1 snapshot; `restic check` termina con "no errors were found".

- [ ] **Step 3: Restore test (validar que el backup sirve)**

```bash
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && source .restic-env
SNAP=$(restic snapshots --json | python3 -c 'import json,sys; print(json.load(sys.stdin)[-1]["short_id"])')
restic restore "$SNAP" --target /tmp/restore-test
echo "=== archivos críticos restaurados ==="
for f in .env homeassistant/secrets.yaml homeassistant/.storage homeassistant/configuration.yaml cloudflared; do
  ls -d /tmp/restore-test/opt/home-automation/$f >/dev/null 2>&1 && echo "OK  $f" || echo "FALTA $f"
done
sudo rm -rf /tmp/restore-test
EOF
```
Expected: `OK` para `.env`, `secrets.yaml`, `.storage`, `configuration.yaml`, `cloudflared` → el backup contiene lo necesario para recovery.

---

### Task 5: Cron

**Files:** ninguno (crontab de root en la R2130).

- [ ] **Step 1: Instalar el cron (04:45, tras el backup local de 04:30)**

```bash
ssh r2130 '(sudo crontab -l 2>/dev/null | grep -v backup-offsite.sh; echo "45 4 * * * /opt/home-automation/scripts/backup-offsite.sh >> /var/log/backup-offsite.log 2>&1") | sudo crontab -'
ssh r2130 'sudo crontab -l | grep backup'
```
Expected: se ven las dos líneas de backup — `30 4 ... backup.sh` (local) y `45 4 ... backup-offsite.sh` (R2).

---

### Task 6: Documentación (MUST)

**Files:**
- Modify: `docs/runbooks/instalacion-r2130.md`, `docs/estado-actual.md`, `docs/runbooks/pendientes.md`

- [ ] **Step 1: `instalacion-r2130.md` — recovery desde R2 + secreto nuevo**

En la sección de backups, agregar:
```markdown
## Backup off-site (restic → Cloudflare R2)
- Diario 04:45 (cron root) vía `scripts/backup-offsite.sh`. Credenciales en `/opt/home-automation/.restic-env` (600, fuera de git).
- Restaurar en una máquina nueva:
  1. Instalar restic; crear `.restic-env` (desde `.restic-env.example`) con las credenciales R2
     y la `RESTIC_PASSWORD` (guardada fuera del R2130).
  2. `source .restic-env && restic snapshots` → elegir snapshot.
  3. `restic restore <id> --target /` (o a un dir y mover) → recupera `/opt/home-automation` completo.
  4. `docker compose up -d`.
- La `RESTIC_PASSWORD` es imprescindible para restaurar: si se pierde, el backup es inrecuperable.
```

- [ ] **Step 2: `estado-actual.md` — backup dual**

En la línea de backups, reflejar:
```markdown
- Backups: (1) local nocturno 04:30 → `/opt/backups` (tar, 14 días); (2) off-site 04:45 → Cloudflare
  R2 con restic (cifrado, incremental, retención 7d/4w/6m). Credenciales en `.restic-env` (fuera de git).
```

- [ ] **Step 3: `pendientes.md` — marcar el punto 1 del hardening**

```markdown
1. ~~Backup off-device cifrado~~ HECHO 2026-09-28: restic → Cloudflare R2 (cron 04:45), restore
   test OK. Password de repo guardada fuera del R2130.
```

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks/instalacion-r2130.md docs/estado-actual.md docs/runbooks/pendientes.md
git commit -m "docs: backup off-site restic/R2 en runbooks y estado"
git push
```

---

## Self-review (cobertura de la spec)

- `.restic-env` (credenciales + password) fuera de git + `.example` versionado → **Task 1** ✓
- Script restic (init, backup con excludes, forget/prune, dead-man) → **Task 2** ✓
- Instalar restic + credenciales + init en R2 → **Task 3** ✓
- Primera corrida + `restic check` + **restore test** → **Task 4** ✓
- Cron 04:45 (tras backup local) → **Task 5** ✓
- Doc MUST (instalacion recovery desde R2, estado backup dual, pendientes) → **Task 6** ✓
- Password crítica fuera del R2130 → **Task 1 (comentario), Task 3 Step 2, Task 6** ✓
- Prerrequisito usuario (bucket/token R2) → header + Task 3 ✓
- Nota: el backup local (backup.sh) se mantiene sin cambios; este es complementario.
