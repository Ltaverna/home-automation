#!/usr/bin/env bash
# Backup nocturno de configs (no media) a /opt/backups. Retiene 14.
# La DB de HA se copia con la API de backup online de SQLite (snapshot consistente,
# integra el WAL) a home-assistant_v2.db.bak, y se respalda ESA copia (no la .db viva).
# El .bak persiste como "última copia consistente" y lo reusa también backup-offsite.sh (04:45).
set -euo pipefail

BACKUP_DIR=/opt/backups/home-automation
SRC=/opt/home-automation
DB=/opt/home-automation/homeassistant/home-assistant_v2.db
DB_SNAP=/opt/home-automation/homeassistant/home-assistant_v2.db.bak
mkdir -p "$BACKUP_DIR"

# Snapshot consistente de la DB. Si sqlite3 no está, se cae al respaldo de la .db viva
# (peor, pero nunca deja la DB fuera del backup).
DB_SNAP_OK=0
if [ -f "$DB" ] && command -v sqlite3 >/dev/null; then
  if sqlite3 "$DB" ".backup '$DB_SNAP'"; then DB_SNAP_OK=1; echo "DB snapshot OK"; fi
fi

if [ "$DB_SNAP_OK" = "1" ]; then
  # excluir la .db viva (y wal/shm); se respalda el .bak consistente
  DB_EXCLUDES=(--exclude='homeassistant/home-assistant_v2.db'
               --exclude='homeassistant/home-assistant_v2.db-wal'
               --exclude='homeassistant/home-assistant_v2.db-shm')
else
  echo "aviso: sin sqlite3, respaldo la .db viva (WAL excluido)"
  DB_EXCLUDES=(--exclude='homeassistant/home-assistant_v2.db-wal'
               --exclude='homeassistant/home-assistant_v2.db-shm')
fi

tar -czf "$BACKUP_DIR/config-$(date +%F).tar.gz" \
    --exclude='frigate/media' \
    "${DB_EXCLUDES[@]}" \
    -C "$(dirname "$SRC")" "$(basename "$SRC")"

ls -1t "$BACKUP_DIR"/config-*.tar.gz | tail -n +15 | xargs -r rm --
