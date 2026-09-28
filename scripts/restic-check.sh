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
