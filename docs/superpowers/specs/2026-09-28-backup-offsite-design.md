# Spec: Backup off-device cifrado (restic → Cloudflare R2)

**Fecha:** 2026-09-28
**Estado:** aprobado
**Contexto:** Punto 1 del hardening pre-Fase 2 (ver `docs/roadmap-evolucion-arquitectura.md` §17-19).
El backup actual (`scripts/backup.sh`, tar local a `/opt/backups`) protege contra errores
operativos pero **no contra disaster** (NVMe muerto, robo, falla física). Falta una copia
cifrada off-site.

## Objetivo

Copia cifrada e incremental de todo lo necesario para reconstruir la instancia, en un destino
externo (Cloudflare R2), con retención y verificación. Complementa —no reemplaza— el backup local.

## Decisiones (del brainstorming)

- **Destino: Cloudflare R2** (S3-compatible; 10 GB gratis + egress gratis; ya usa Cloudflare).
- **Herramienta: restic** (dedup + incremental + cifrado nativo).
- **Ejecución: host + cron** (como el backup local; más robusto que en contenedor; restic lee
  archivos del host). Se mantiene el backup local.
- **Password de repo restic: crítica**, se guarda **fuera del R2130** (gestor del usuario).

## Componentes

### Credenciales — `/opt/home-automation/.restic-env` (fuera de git, chmod 600)
```sh
export RESTIC_REPOSITORY="s3:https://<account_id>.r2.cloudflarestorage.com/<bucket>"
export AWS_ACCESS_KEY_ID="<r2_access_key_id>"
export AWS_SECRET_ACCESS_KEY="<r2_secret_access_key>"
export RESTIC_PASSWORD="<password-repo-restic>"   # también guardada fuera del R2130
export BACKUP_HC_URL="https://hc-ping.com/<uuid-backup>"  # healthchecks del backup (opcional)
```
Se agrega `.restic-env` a `.gitignore`. Se versiona `.restic-env.example` (nombres + descripción,
sin valores).

### Script — `scripts/backup-offsite.sh`
1. `source /opt/home-automation/.restic-env`.
2. `restic snapshots` → si el repo no existe aún, `restic init` (primera corrida).
3. `restic backup` de `/opt/home-automation` con `--exclude`:
   - `frigate/media`, `**/__pycache__`, `*.log`, `*.log.*`, `homeassistant/home-assistant_v2.db-wal`,
     `homeassistant/home-assistant_v2.db-shm`, `/opt/backups` (no meter el tar local dentro).
4. `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune`.
5. Si todo salió OK y `BACKUP_HC_URL` está definido → `curl -fsS "$BACKUP_HC_URL"` (dead-man).
6. `set -euo pipefail` + log a stdout (lo captura cron/journal). Si falla, NO pinguea el
   healthcheck → healthchecks.io alerta "backup falló/atrasado".

### Cron
Nueva línea en el crontab de root de la R2130, **después** del backup local (04:30):
```
45 4 * * * /opt/home-automation/scripts/backup-offsite.sh >> /var/log/backup-offsite.log 2>&1
```

## Qué se respalda (incluido en el snapshot)

Todo `/opt/home-automation` salvo los excludes → cubre: repo, `.env`, `secrets.yaml`,
`homeassistant/.storage` (pairings/tokens/entity registry), `homeassistant/custom_components`,
`mosquitto/data` + `mosquitto/config/passwd`, `cloudflared/*.json`, `face-embed/data` (DB de caras),
`.restic-env` (queda dentro del snapshot; ojo: el snapshot está cifrado, pero la password de repo
NO debe depender solo de ahí → por eso se guarda también fuera del R2130).

## Setup que hace el usuario (una vez)

1. Cloudflare → R2 → crear bucket (ej. `r2130-backup`).
2. R2 → Manage API Tokens → crear token con permiso Object Read & Write sobre ese bucket →
   obtener Access Key ID + Secret Access Key + el account_id (del endpoint).
3. Elegir una password de repo restic fuerte y **guardarla en su gestor** (fuera del R2130).
4. Pasar esos 5 valores para completar `.restic-env` en la R2130.

## Verificación de éxito

- `restic snapshots` lista al menos un snapshot en R2 tras la primera corrida.
- `restic check` sin errores (integridad del repo).
- **Restore test** (enlaza con el punto 2 del hardening): `restic restore <id> --target /tmp/restore-test`
  y verificar que aparecen `.storage`, `secrets.yaml`, `.env`, etc.
- El cron queda instalado; una corrida manual del script termina con exit 0 y (si configurado)
  pinguea el healthcheck.
- `.restic-env` en `.gitignore` (no se filtra a git); `.restic-env.example` versionado.

## Documentación (MUST)

- `scripts/backup-offsite.sh` autocomentado.
- `docs/runbooks/instalacion-r2130.md`: agregar el backup off-site al recovery (cómo restaurar
  desde R2 con restic) y a la lista de secretos (`.restic-env`).
- `docs/estado-actual.md`: mencionar el backup dual (local + R2 cifrado).
- `docs/runbooks/pendientes.md`: marcar el punto 1 del hardening como HECHO.
- `.env.example`/`.restic-env.example` documentados.

## Fuera de alcance

- Recovery test completo desde cero en hardware limpio (es el punto 2 del hardening; acá solo se
  hace un restore test parcial para validar el backup).
- Backup de los otros proyectos de la R2130 (crypto-bot, consorcio) — fuera de este repo.
- Observabilidad de "edad del backup" como sensor en HA (el dead-man de healthchecks ya cubre
  el caso "no corrió"; un sensor de edad se puede sumar en el punto 3, observabilidad de nodo).
