# Upgrades de imágenes Docker

Las imágenes críticas están **pinneadas** en `docker-compose.yml` (nada de `latest`/`stable`):
un `docker compose pull`/recreate NO actualiza sin editar el repo.

## Versiones actuales (2026-09-28)
- `ghcr.io/home-assistant/home-assistant:2026.9.3`
- `cloudflare/cloudflared:2026.9.3`
- `eclipse-mosquitto:2` @ `sha256:38c0da4f…` (broker 2.1.2; la línea 2.1.x solo se publica como
  `-alpine`, así que se pinnea por digest inmutable de la imagen Debian que corre).

### Cómo bumpear mosquitto (pin por digest)
El `:2` es un tag móvil; para actualizar de forma controlada: `docker pull eclipse-mosquitto:2`,
mirar el nuevo digest con `docker image inspect eclipse-mosquitto:2 --format '{{index .RepoDigests 0}}'`,
y pegar ese `@sha256:…` en `docker-compose.yml`.

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
