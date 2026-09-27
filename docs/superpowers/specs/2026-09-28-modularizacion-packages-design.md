# Spec: Modularización de la config de HA en packages

**Fecha:** 2026-09-28
**Estado:** aprobado
**Contexto:** Segundo sub-proyecto del refactor de arquitectura (después de Observabilidad).
Hoy la config de HA es monolítica (`automations.yaml` ~19 automatizaciones, `scripts.yaml` ~13
scripts, `configuration.yaml` con helpers mezclados). Objetivo: reorganizar por feature para
mantenibilidad y para que Fase 2 (Zigbee/sensores) sume un package en vez de engordar los
monolitos.

## Decisiones (del brainstorming)

- **Todo por git** (nunca se edita por la UI de HA) → **packages puros**: cada feature 100%
  autocontenido en su archivo. Se quitan los `automation:`/`script: !include` monolíticos.
- **Granularidad fina, por feature**.
- Los `entity_id` y los `id` de automatizaciones **no cambian** (es mover texto, no renombrar) →
  nada aguas abajo (dashboards, MCP, scripts que se llaman entre sí) se rompe.

## Mecanismo

En `configuration.yaml`, dentro del bloque `homeassistant:`:
```yaml
homeassistant:
  ...
  packages: !include_dir_named packages/
```
HA mergea todos los archivos de `packages/` al arrancar. Cada package puede declarar
`automation:`, `script:`, `input_boolean:`, `input_select:`, `timer:`, etc. Las listas
(automation/script) de los distintos packages se concatenan.

## Mapeo feature → package

| Package | Contenido |
|---|---|
| `packages/tv.yaml` | `wake_on_lan`; template switches (flow/netflix/youtube × sala/dormitorio); `rest_command.st_tv_dormitorio_app`; scripts `tv_living_encender`, `tv_dormitorio_encender`, `tv_app`, `flow_canal`, `flow_sala`, `netflix_sala`, `youtube_sala`, `tv_app_dormitorio`, `flow_dormitorio`, `netflix_dormitorio`, `youtube_dormitorio`, `flow_canal_dormitorio`; automations `tv_living_wol`, `webhook_flow_sala`, `webhook_netflix_sala`, `webhook_youtube_sala`, `homekit_remote_lg` |
| `packages/house_mode.yaml` | `input_select.house_mode`; automations `house_mode_llegada`, `house_mode_salida`, `house_mode_noche`, `house_mode_manana`, `despertar_suave` |
| `packages/paseo.yaml` | `input_boolean.modo_paseo`; `timer.paseo`; `script.iniciar_paseo`; automations `modo_paseo_inicio`, `modo_paseo_fin` |
| `packages/seguridad.yaml` | `input_boolean.modo_simulacion`; automations `simulacion_toggle`, `simulacion_fin`, `aviso_tv_away`, `aviso_tv_apagar` |
| `packages/face.yaml` | `input_boolean.lucas_visto_camara`; automations `face_reconocido`, `face_lucas_presencia` |
| `packages/salud.yaml` | automation `salud_alerta` |

## Qué queda en `configuration.yaml` (core/infra transversal)

- `default_config`, `http` (proxy), `homeassistant` (name/tz/URLs) + la línea `packages:`.
- `homekit` (2 instancias) — **transversal** (expone switches de TV + input_boolean de
  paseo/simulación), por eso queda en core y no en un package.
- `lovelace` (dashboards).
- **Se eliminan** `automation: !include automations.yaml` y `script: !include scripts.yaml`
  (todo migra a packages). `scene: !include scenes.yaml` se mantiene (o se elimina si queda vacío).
- Los archivos `automations.yaml` y `scripts.yaml` quedan vacíos o se borran del repo tras migrar.

## Enfoque incremental (mitiga el riesgo de tocar producción)

Un package por commit, y en cada paso:
1. Crear `packages/<feature>.yaml` con el contenido movido.
2. Quitar ese contenido de su origen (`automations.yaml`/`scripts.yaml`/`configuration.yaml`).
3. `check_config` → sin ERROR.
4. Deploy (pull) + restart HA.
5. Verificar que el conjunto de automatizaciones/scripts/entidades no cambió (conteo y nombres).

El bloque `packages:` en `configuration.yaml` se agrega en el primer paso; el borrado de los
`!include` monolíticos se hace en el último (cuando `automations.yaml`/`scripts.yaml` ya están
vacíos), para no dejar HA sin esas keys en el medio.

## Verificación de éxito

- **Antes**: capturar la lista de `automation.*`, `script.*` y helpers (input_*, timer.*).
- **Después**: la lista es idéntica (mismos entity_id, ninguno de menos ni duplicado).
- `check_config` limpio en cada paso.
- Prueba funcional: disparar una automatización (ej. `salud_alerta` o un `flow_canal`) y un
  script post-refactor → siguen funcionando.
- `docker restart homeassistant` arranca sin errores en el log.

## Dependencias cruzadas (contempladas, no son problema)

HA resuelve `entity_id` globalmente, sin importar en qué archivo estén:
- `despertar_suave` (house_mode) → `script.flow_canal_dormitorio` (tv).
- `house_mode_salida` (house_mode) → condición sobre `input_boolean.modo_paseo` (paseo).
- `aviso_tv_away` (seguridad) → condición sobre `input_boolean.modo_simulacion` (seguridad) y TVs (tv).

## Archivos

- Create: `packages/tv.yaml`, `packages/house_mode.yaml`, `packages/paseo.yaml`,
  `packages/seguridad.yaml`, `packages/face.yaml`, `packages/salud.yaml`
  (bajo `homeassistant/packages/`).
- Modify: `homeassistant/configuration.yaml` (agregar `packages:`, quitar los `!include` monolíticos).
- Delete/vaciar: `homeassistant/automations.yaml`, `homeassistant/scripts.yaml`.

## Fuera de alcance

- Parametrización a `secrets.yaml` (tercer sub-proyecto, va después sobre esta base modular).
- Reorganizar dashboards (ya están en `dashboards/`, quedan como están).
- Cambiar lógica de automatizaciones (esto es solo mover, no modificar comportamiento).
