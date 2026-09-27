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
