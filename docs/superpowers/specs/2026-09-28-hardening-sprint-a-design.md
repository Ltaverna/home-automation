# Spec: Hardening Sprint A (pre-Fase 2)

**Fecha:** 2026-09-28
**Estado:** aprobado (pendiente revisión del usuario)
**Origen:** `docs/development-handoff-sprint-a-f.md` (handoff de ChatGPT, 2026-09-27), bloque
**Sprint A — Hardening** (P0). Los sprints B–F (presencia física, Frigate, visión, semántico)
esperan la compra USA y no entran en este ciclo.

## Objetivo

Cerrar la deuda técnica y de seguridad de la plataforma actual antes de sumar servicios pesados
(Zigbee, cámaras). Todo verificable sin hardware nuevo. Siete items independientes, un solo plan.

## Principios que aplican (del handoff §3)

Local-first · manual-first · deterministic-first · observable. Nada de infraestructura enterprise
(sin Prometheus/Grafana/K8s). Las acciones críticas no dependen de IA.

---

## Item 1 — Fix `check_mcp` en healthmon (bug real)

**Problema (verificado):** `healthmon/monitor.py::check_mcp()` hace `requests.get()` y devuelve
`True, "ok"` ante *cualquier* respuesta HTTP; solo marca caído si falla la conexión TCP. El
endpoint MCP hoy responde **404** en `/`, `/health` y `/mcp` — o sea el chequeo actual reporta
"sano" con un 404. Un 5xx también pasaría como sano.

**Diseño:**
- Reescribir `check_mcp()` para distinguir *transporte vivo* de *error de servidor*:
  - respuesta con `status_code < 500` → UP (el server ha_mcp_tools responde, aunque sea 404 en `/`;
    el 404 es normal, el MCP vive en `/<secret_path>`).
  - `status_code >= 500` → DOWN (`HTTP {code}`).
  - excepción de conexión / timeout → DOWN.
- `ha_mcp_tools` **no expone** un `/health` propio (verificado: 404). No se inventa uno; el chequeo
  de liveness por status es suficiente y coherente con `check_http` ya existente.
- Anti-flapping: healthmon ya publica estado cada `INTERVAL` (60s); la automatización `salud_alerta`
  ya notifica por transición. No se agrega histéresis nueva (YAGNI).

**Acceptance (handoff §4):** MCP detenido → DOWN · MCP responde 500 → DOWN · MCP operativo (404 en
`/`) → UP · timeout → DOWN · visible en HA (`binary_sensor.salud_mcp`).

---

## Item 2 — Corregir `external_url` de HA (bug real)

**Problema (verificado):** `homeassistant/configuration.yaml:19` tiene
`external_url: "https://ha-mcp.neuralcore.dev"`. Ese dominio sirve el **MCP** (404), no el login de
HA. `ha_mcp_tools` usa `homeassistant.helpers.network.get_url` (que lee `external_url`) como base de
URLs de token/OAuth, y su propia doc exige que esa URL "llegue a la página de login de HA, sin puerto".
Además rompe links generados y notificaciones accionables fuera de casa.

**Decisión (usuario):** apuntar `external_url` a la URL de Tailscale.

**Diseño:**
- `external_url: "https://r2130.tail71f19f.ts.net"` (Tailscale serve → :8123; llega al login de HA,
  sin puerto → cumple lo que pide `ha_mcp_tools`).
- `internal_url` queda `http://192.168.1.17:8123`.
- El connector MCP **no se toca**: sigue usando su propio `server_url`
  (`https://ha-mcp.neuralcore.dev`), que es transporte independiente del `external_url` de HA.
- **Verificación post-cambio (crítica):** tras reiniciar HA, confirmar que el connector MCP sigue
  conectando (el uso es secret_path, no OAuth con base en get_url, así que no debería romperse; se
  verifica igual). Si algo del MCP dependiera de get_url, se documenta y se revierte.

**Acceptance (handoff §7):** URL MCP y URL HA con semántica clara y separada; no se usa la URL del
MCP como canonical de HA; decisión documentada (README/estado-actual). Connector MCP sigue vivo.

---

## Item 3 — Pinnear imágenes Docker

**Problema (verificado):** `homeassistant:stable` y `cloudflared:latest` son tags móviles; un
`docker compose pull`/recreate puede actualizar sin querer. `mosquitto:2` es pin de major (aceptable
pero se fija exacto por consistencia).

**Versiones corriendo hoy (a pinnear):**
- `ghcr.io/home-assistant/home-assistant:2026.9.3`
- `cloudflare/cloudflared:2026.9.3`
- `eclipse-mosquitto:2.1.2`

**Diseño:**
- Fijar los tags exactos en `docker-compose.yml`.
- Documentar en un runbook nuevo `docs/runbooks/upgrades.md` el proceso: revisar release → bump tag
  en el repo → `git pull` en R2130 → `docker compose pull && up -d` → health checks (vista Salud +
  `binary_sensor.salud_*`) → rollback (revertir el tag y `up -d`).

**Acceptance (handoff §6):** ninguna imagen crítica usa `latest`/`stable`; versión actual
documentada; rollback documentado; `docker compose pull` no cambia versión sin editar el repo.

---

## Item 4 — Separar `face-api` / `face-loop` por profile

**Problema (verificado):** `face-embed` y `face-recognizer` comparten `profiles: ["face"]` con
`restart: unless-stopped`. La casa principal (`COMPOSE_PROFILES=face,obs`) al hacer
`docker compose up -d` **arrancaría el loop de cámara** (`/dev/video0` cada ~4s). El "pausado" actual
es un `docker stop` manual — frágil, no sobrevive un `compose up`.

**Diseño:**
- Renombrar contenedores/servicios conceptualmente a **face-api** (el actual `face-embed`, API de
  inferencia, profile `face`) y **face-loop** (el actual `face-recognizer`, profile
  `experimental`). Para no romper entidades/DB ni el historial, se mantienen los **nombres de
  servicio y `container_name` actuales** (`face-embed`, `face-recognizer`); el cambio es de **profile**:
  - `face-embed` → profile `face` (o `face-api`).
  - `face-recognizer` → profile `experimental` (ya no `face`).
- Actualizar `.env.example` y el `.env` de la casa principal: `COMPOSE_PROFILES=face,obs`
  (sin `experimental`) → `up -d` normal **no** inicia captura de cámara.
- Documentar ambos componentes en README (roles + qué profile los levanta).

**Acceptance (handoff §5):** `docker compose up -d` normal NO inicia captura periódica; `face-api`
(face-embed) arranca solo; el loop requiere profile explícito (`experimental`); README lo documenta;
no hay dos procesos por la misma cámara.

---

## Item 5 — Backups: `restic check` + antigüedad + DB consistente

**Problema (verificado):** `backup-offsite.sh` tiene `forget/prune` pero **no** `restic check`
(integridad). No hay sensor de antigüedad del backup. `backup.sh` tar-ea `home-assistant_v2.db` en
vivo **excluyendo** el WAL → snapshot potencialmente inconsistente.

**Diseño (3 sub-cambios):**

1. **DB consistente (decisión usuario: sqlite3 `.backup` online).** En `backup.sh`, antes del tar:
   `docker exec homeassistant python -c "..."` **o** `sqlite3` en el host — usar la API de backup
   online de SQLite para volcar una copia consistente a `homeassistant/backup/home-assistant_v2.db`
   (o `/tmp`), y tar-ear **esa** copia en vez de la `.db` viva. Deja de excluir/incluir WAL a mano:
   la copia `.backup` ya integra el WAL. Comando: `sqlite3 <src> ".backup <dst>"` (requiere sqlite3
   en el host; si no está, `apt install sqlite3`, o usar el `python3 -c "import sqlite3; ..."` del
   contenedor HA que ya tiene sqlite3).

2. **`restic check` semanal.** Nuevo `scripts/restic-check.sh` (reusa `.restic-env`), cron **semanal**
   (ej. domingo 05:15), NO en cada backup. Loguea y pinguea un healthcheck propio (opcional). Corre
   como root (igual que backup-offsite).

3. **Sensor `sensor.last_backup_age`.** Para no consultar R2 cada minuto: `backup-offsite.sh`
   escribe un **marker local** (`/opt/home-automation/.last-backup-offsite`, con `date -Is`) al
   terminar OK. `scripts/node-metrics.sh` lee ese archivo (mtime / contenido) y publica la antigüedad
   en horas por MQTT Discovery → `sensor.last_backup_age` (unit `h`, device "Nodo R2130"). Cero
   dependencia de red en el tick de 1 min. Alerta en `packages/salud.yaml` (extiende `nodo_alerta` o
   nueva): `> 36 h` → notif accionable "Backup off-site atrasado".

**Acceptance (handoff §9):** backup local diario ✓ (ya) · off-site cifrado ✓ (ya) · retención ✓ (ya)
· `restic check` periódico (nuevo) · alerta de backup stale (nuevo) · restore runbook actualizado ·
DB respaldada de forma consistente (nuevo).

---

## Item 6 — CI mínimo (GitHub Actions)

**Contexto:** el repo vive en GitHub (`Ltaverna/home-automation`); la R2130 solo pullea (deploy key
read-only). CI corre en GitHub, sin tocar la R2130. El repo tuvo IDs-credencial en su historia
(webhooks, ya eliminados) → un scanner de secretos aporta valor real.

**Diseño:** `.github/workflows/ci.yml` con jobs baratos en push/PR:
- **yaml-lint**: validar sintaxis de los YAML (`yamllint` con config laxa, o `python -c yaml.safe_load`).
- **compose-config**: `docker compose config -q` (valida el compose; secrets vía dummy `.env`).
- **secrets-scan**: `gitleaks` (action oficial) sobre el repo/diff.
- (Opcional) **ruff** sobre los servicios propios en Python (`healthmon`, `face-embed`,
  `face-recognizer`) — sin `pytest` por ahora (no hay tests; YAGNI).

**Acceptance (handoff §37):** PR corre syntax + secrets scan + compose config; falla si hay YAML roto,
secreto, o compose inválido.

---

## Item 7 — Hardening MCP: Cloudflare Access/Portal + hardening local

**Decisión (usuario): Portal completo con API token.** Yo scripteo la Access application + policy
end-to-end; el usuario testea los connectors después.

**Contexto verificado:** `ha_mcp_tools` ya trae un **deny floor no-anulable** sobre `.storage` y
`secrets.yaml` para sus tools de archivo (`const.py`, `DENY_PATH_SEGMENTS`), más allowlist de
directorios configurable. El transporte es el túnel `ha-mcp.neuralcore.dev` → `:9584`, auth por
`secret_path`. Cloudflare MCP Server Portals (open beta, incluido en Zero Trust free hasta 50
usuarios) permiten poner **Access** (identidad + MFA + logging) delante.

**Diseño (dos partes):**

**A. Cloudflare Access/Portal (scripted vía API token):**
- **Credencial:** el usuario deja el API token de Cloudflare en `~/.cloudflare-token` (600) en el
  mini-PC. **No se pega en el chat.** El token necesita permisos de Access (Zero Trust) sobre la
  cuenta y la zona `neuralcore.dev`.
- Script `scripts/cf-access-mcp.sh` (o pasos vía `curl` a la API de Cloudflare) que:
  1. descubre account_id / zone_id de `neuralcore.dev`,
  2. crea una **Access self-hosted application** para `ha-mcp.neuralcore.dev` (o un MCP Server Portal),
  3. crea una **policy** que permita solo la identidad de Lucas (email `lucas@bold-agro.ai`, login por
     OTP email o Google),
  4. deja el logging de Access activo.
- **secret_path se mantiene** como defensa en profundidad (Access = puerta de identidad; secret_path
  = segunda capa). Sacarlo se evalúa después, no en este sprint.
- **Verificación (usuario):** reconectar el connector en ChatGPT y Claude; confirmar que aparece el
  login de Access y que tras autenticar el MCP responde. Riesgo conocido: doble capa OAuth (Access +
  DCR de ha_mcp_tools) puede requerir ajuste; si el connector no completa el login, se documenta el
  problema y se deja Access en modo que no rompa (o se revierte la policy) sin perder el estado previo.

**B. Hardening local (automatizable, sin depender de Cloudflare):**
- Verificar/documentar el deny floor (`.storage`, `secrets.yaml`) del componente.
- Revisar qué entidades están **expuestas a Assist** (las tools del MCP operan sobre esas); limitar a
  las necesarias (TVs, house_mode, escenas, luces futuras) y **no** exponer nada sensible. Documentar
  la lista.
- Documentar la **rotación del secret_path** (`regenerate_secrets` en el options flow) y el plan de
  migración a OAuth puro como norte.

**Acceptance (handoff §8):** autenticación explícita (Access) delante del MCP + secret_path como
segunda capa; tools/entidades acotadas y documentadas; logging de acceso (Access); secrets no
hardcodeados; el MCP no expone unlock/shell/arbitrary (no existen hoy; DDL615 fuera de alcance de
tools por decisión previa).

---

## Orden de implementación (bugs primero)

1. Item 1 — fix healthmon MCP (bug, aislado).
2. Item 2 — external_url (bug, requiere restart HA + re-test MCP).
3. Item 3 — pin imágenes + runbook upgrades.
4. Item 4 — split face profiles + `.env`.
5. Item 5 — backups (DB consistente → restic check → sensor+alerta).
6. Item 6 — CI (GitHub Actions).
7. Item 7 — MCP: (B) hardening local primero (automatizable) → (A) Cloudflare Access/Portal cuando el
   usuario deje el token en `~/.cloudflare-token`.

## Verificación de éxito (global)

- `binary_sensor.salud_mcp` reacciona correcto a 5xx / stop / 404 / timeout.
- `external_url` = Tailscale; connector MCP sigue vivo; `check_config` limpio.
- `docker compose config` muestra tags exactos; `up -d` en la casa principal no arranca `face-recognizer`.
- Backup local produce una `.db` consistente; `restic check` semanal en cron; `sensor.last_backup_age`
  visible en la vista Salud con alerta > 36 h.
- CI corre en el próximo push (yaml + compose + gitleaks verdes).
- MCP detrás de Access con la identidad de Lucas; secret_path como segunda capa; entidades acotadas.

## Documentación (MUST)

- `docs/estado-actual.md`: fixes (healthmon, external_url), split face profiles, backups nuevos, MCP
  detrás de Access.
- `docs/runbooks/pendientes.md`: marcar Sprint A hecho; abrir "Fase 2 (presencia física)" como norte.
- `docs/runbooks/upgrades.md` (nuevo): pinning + proceso de upgrade/rollback.
- `docs/runbooks/instalacion-r2130.md`: nota de restore con DB consistente + `restic check`.
- `README.md`: roadmap (Sprint A ✅), face-api/face-loop, CI, MCP+Access.

## Fuera de alcance (este sprint)

- Sprints B–F del handoff (presencia física, Frigate, visión, semántico, edge AI, agentic): esperan
  compra USA.
- Migración del MCP a OAuth puro (sacar el secret_path): se evalúa después de validar Access.
- `pytest` para los servicios propios: no hay tests hoy; se suma cuando haya lógica que lo justifique.
- House Mode v2 / contextos (handoff §12): es diseño de Fase 2, no hardening.
