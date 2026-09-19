#!/usr/bin/env bash
# Backup nocturno de configs (no media) a /opt/backups. Retiene 14.
set -euo pipefail

BACKUP_DIR=/opt/backups/home-automation
SRC=/opt/home-automation
mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/config-$(date +%F).tar.gz" \
    --exclude='frigate/media' \
    --exclude='homeassistant/home-assistant_v2.db-wal' \
    --exclude='homeassistant/home-assistant_v2.db-shm' \
    -C "$(dirname "$SRC")" "$(basename "$SRC")"

ls -1t "$BACKUP_DIR"/config-*.tar.gz | tail -n +15 | xargs -r rm --
