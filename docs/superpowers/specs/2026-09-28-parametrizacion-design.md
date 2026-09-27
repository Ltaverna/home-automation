# Spec: Parametrización casa-específica

**Fecha:** 2026-09-28
**Estado:** aprobado
**Contexto:** Tercer y último sub-proyecto del refactor de arquitectura (tras Observabilidad y
Modularización). Objetivo: portabilidad a una segunda casa "independiente y similar" y dejar
los valores casa-específicos identificados/aislados. Se apoya en la base modular (packages/).

## Realidad técnica (marca el alcance)

HA **no** permite parametrizar con `!secret`:
- `entity_id:` en targets (deben ser literales).
- Valores dentro de templates Jinja `{{ }}` (ej. los IDs Tizen en el `state:` de los switches).

Por eso el enfoque es **pragmático en 3 capas**, no "todo parametrizado".

## Decisiones (del brainstorming)

- Enfoque **pragmático**: `secrets.yaml` para lo que se puede limpio + convención + doc onboarding.
- **compose profiles** por módulo (activar/desactivar servicios pesados por casa).
- **Documentación es un MUST**: se actualiza en el mismo ciclo (requisito explícito, no opcional).

## Capa 1 — A `secrets.yaml` (valores en `data:`/URLs, no en templates)

Mover a `homeassistant/secrets.yaml` (fuera de git; ya existe con `st_bearer`):
| Secret | Valor actual | Usado en |
|---|---|---|
| `lg_mac` | `38:06:E6:1C:26:70` | `script.tv_living_encender` (`mac: !secret lg_mac`) |
| `samsung_mac` | `68:72:C3:80:C4:A8` | `script.tv_dormitorio_encender` |
| `st_url` | `https://api.smartthings.com/v1/devices/bf18b0f0-0a56-6be5-a574-26ef4efdb123/commands` | campo `url` del `rest_command.st_tv_dormitorio_app` (`url: !secret st_url`) |

Verificar que `secrets.yaml` esté en `.gitignore` (ya lo está). Documentar cada clave en un
`secrets.yaml.example` (nombres + descripción, sin valores) versionado en git.

**Nota sobre el device_id:** `!secret` reemplaza el valor completo de un campo escalar, no
interpola dentro de un string. Como el device_id vive embebido en la URL del `rest_command`, la
forma limpia es mover **la URL completa** a `secrets.yaml` como `st_url` y usar `url: !secret st_url`
(en vez de intentar interpolar solo el id). Así el dato casa-específico queda fuera de git.

## Capa 2 — No parametrizable → convención + doc

- **entity_ids** (`media_player.lg_webos_tv_oled55c3psa`, `media_player.tv_dormitorio`,
  `remote.tv_dormitorio`, etc.): en una casa nueva, **renombrar las entidades tras el pairing**
  para que coincidan con las que usan los packages. Documentado en el onboarding con la lista de
  entity_ids esperados.
- **IDs Tizen** (`fCCrJTSe28.Flow`, `org.tizen.netflix-app`, `9Ur5IzDKqV.TizenYouTube`) en los
  templates de los switches (`packages/tv.yaml`) y los scripts `*_dormitorio`: son casa-específicos
  (cada Samsung puede tener otros). Quedan en el package; el onboarding explica cómo recapturarlos.
- **Grilla Flow** (`packages/tv.yaml`): casa-específica por zona; ya tiene la nota de "corregir
  contra la TV real". El onboarding lo menciona.
- **secret_path del MCP** y **hostname Cloudflare**: viven en `.storage` (config entry de
  `ha_mcp_tools`) y en `cloudflared/config-mcp.yml` (hostname + tunnel id). Casa nueva → su propio
  túnel/subdominio. Documentado.

## Capa 3 — compose profiles

En `docker-compose.yml`, agregar `profiles:` a los servicios pesados:
- `face-embed`, `face-recognizer` → profile `face` (requieren Hailo + cámara).
- `healthmon` → profile `obs` (opcional).
- Base **sin profile** (siempre levanta): `mosquitto`, `homeassistant`, `cloudflared-mcp`.

Activación por casa vía `COMPOSE_PROFILES` en el `.env` (ej. `COMPOSE_PROFILES=face,obs` en la
casa principal; vacío o `obs` en una casa sin Hailo). Documentar en `.env.example`.

**Verificar** que en la R2130 (casa principal) el `.env` tenga `COMPOSE_PROFILES=face,obs` para
que TODO siga levantando igual que hoy (no romper la instalación actual).

## El entregable estrella: doc de onboarding

`docs/runbooks/onboarding-casa-nueva.md` — checklist para instalar en una casa nueva:
1. Pi OS + Docker (referencia al runbook de instalación).
2. `git clone` del repo.
3. Completar `.env` (desde `.env.example`): TZ, MQTT, `HEALTHCHECKS_URL`, `COMPOSE_PROFILES`.
4. Completar `homeassistant/secrets.yaml` (desde `secrets.yaml.example`): `st_bearer`, `lg_mac`,
   `samsung_mac`, `st_url`.
5. `docker compose up -d` (levanta según profiles).
6. Onboarding de HA + parear dispositivos, **renombrar entidades con la convención** (lista de
   entity_ids esperados en el doc).
7. Recapturar lo casa-específico: IDs Tizen de apps del Samsung, grilla Flow de la zona, crear
   túnel Cloudflare propio + subdominio, check de healthchecks.io.
8. Verificar con la vista "Salud" y `check_config`.

## Documentación (MUST, parte del entregable)

Actualizar en el mismo ciclo:
- `secrets.yaml.example` (nuevo, versionado) + `.env.example` (profiles).
- `README.md` (mencionar secrets/profiles/onboarding).
- `docs/estado-actual.md` (nota de parametrización).
- `docs/runbooks/pendientes.md` (marcar los 3 sub-proyectos del refactor como HECHOS).
- `docs/runbooks/instalacion-r2130.md` (referenciar el onboarding).

## Verificación de éxito

- `secrets.yaml` con las 4 claves; los packages usan `!secret`; `check_config` limpio.
- El sistema sigue **idéntico** en runtime (los `!secret` resuelven a los valores actuales →
  WoL, apps del Samsung, etc. funcionan igual). Prueba: encender una TV por WoL y lanzar una app.
- `docker compose config` válido; con `COMPOSE_PROFILES=face,obs` levantan los 6 servicios (igual
  que hoy); sin profiles, solo la base.
- Doc de onboarding completo y sin placeholders.

## Fuera de alcance

- Instalar realmente la segunda casa (esto deja la base lista, no ejecuta la instalación).
- Parametrizar entity_ids / IDs Tizen / grilla (imposible/no vale — se cubren por convención+doc).
- Multi-casa gestionada centralmente (cada casa es una instancia independiente del repo).
