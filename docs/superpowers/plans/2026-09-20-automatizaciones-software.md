# Automatizaciones de software puro — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar 4 automatizaciones (despertar suave, modo paseo, aviso TV+AWAY, presencia simulada) usando solo entidades ya integradas, según `docs/superpowers/specs/2026-09-20-automatizaciones-software-design.md`.

**Architecture:** Todo declarativo en los YAML de HA. Helpers nuevos (`input_boolean`, `timer`) en `configuration.yaml`; lógica en `automations.yaml` y `scripts.yaml`. Workflow: editar en el mini-PC → `check_config` → commit/push → `git pull` en la R2130 → reload (o restart si tocó `configuration.yaml`) → verificar disparando por API.

**Tech Stack:** Home Assistant (YAML), API REST de HA, notificaciones accionables de la app iOS.

**Convención de verificación:** HA no tiene tests unitarios para config declarativa. Cada task se "testea" con: (1) `check_config` sin errores, (2) la entidad/automatización aparece en la API, (3) disparo manual que produce el efecto esperado. Comandos desde el mini-PC; token en `~/.ha_token`.

```bash
# Helpers de shell usados en todo el plan (pegar al inicio de cada sesión de terminal):
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
deploy() { ssh r2130 'git -C /opt/home-automation pull -q'; }
checkcfg() { ssh r2130 'docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -3'; }
reload_auto() { curl -sS -m 10 -X POST -H "$H" $BASE/services/automation/reload >/dev/null && echo "automations recargadas"; }
reload_script() { curl -sS -m 10 -X POST -H "$H" $BASE/services/script/reload >/dev/null && echo "scripts recargados"; }
```

---

### Task 1: Helpers (input_boolean + timer) y filtro HomeKit

**Files:**
- Modify: `homeassistant/configuration.yaml`

- [ ] **Step 1: Agregar los helpers**

En `homeassistant/configuration.yaml`, después del bloque `template:` (antes de `# Dashboard "Control remoto"`), agregar:

```yaml
# Helpers para automatizaciones de software puro (spec 2026-09-20)
input_boolean:
  modo_paseo:
    name: Modo paseo
    icon: mdi:dog-side
  modo_simulacion:
    name: Modo simulación (anti-robo)
    icon: mdi:shield-home

timer:
  paseo:
    name: Paseo perro
    duration: "00:30:00"
    restore: true
```

- [ ] **Step 2: Exponer los switches a HomeKit**

En `configuration.yaml`, en el filtro del bridge `HASS Bridge` (puerto 21063), agregar las dos líneas al final de `include_entities`:

```yaml
        - switch.youtube_dormitorio
        - input_boolean.modo_paseo
        - input_boolean.modo_simulacion
```

(la primera línea ya existe; agregar solo las dos de `input_boolean`).

- [ ] **Step 3: Validar config**

```bash
git add homeassistant/configuration.yaml && git commit -m "feat: helpers modo_paseo/modo_simulacion + timer paseo"
git push && deploy && checkcfg
```
Expected: `check_config` termina sin líneas de ERROR.

- [ ] **Step 4: Restart (los helpers YAML nuevos requieren reinicio) y verificar**

```bash
ssh r2130 'docker restart homeassistant' && sleep 40
curl -sS -m 5 -H "$H" $BASE/states/input_boolean.modo_paseo | python3 -c 'import json,sys; print("modo_paseo =", json.load(sys.stdin)["state"])'
curl -sS -m 5 -H "$H" $BASE/states/input_boolean.modo_simulacion | python3 -c 'import json,sys; print("modo_simulacion =", json.load(sys.stdin)["state"])'
curl -sS -m 5 -H "$H" $BASE/states/timer.paseo | python3 -c 'import json,sys; d=json.load(sys.stdin); print("timer.paseo =", d["state"], "| dur:", d["attributes"].get("duration"))'
```
Expected: `modo_paseo = off`, `modo_simulacion = off`, `timer.paseo = idle | dur: 0:30:00`.

---

### Task 2: Despertar suave

**Files:**
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar la automatización**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: despertar_suave
  alias: "Despertar suave"
  description: "08:30 lun-vie estando en casa: TV dormitorio en Flow canal 14."
  triggers:
    - trigger: time
      at: "08:30:00"
  conditions:
    - condition: time
      weekday: [mon, tue, wed, thu, fri]
    - condition: state
      entity_id: person.lucas
      state: "home"
  actions:
    - action: script.flow_canal_dormitorio
      data:
        canal: 14
```

- [ ] **Step 2: Validar y desplegar**

```bash
git add homeassistant/automations.yaml && git commit -m "feat: despertar suave (TV dormitorio Flow canal 14, 08:30 L-V)"
git push && deploy && checkcfg && reload_auto
```
Expected: `check_config` sin ERROR; "automations recargadas".

- [ ] **Step 3: Verificar que existe y probar el efecto**

```bash
curl -sS -m 5 -H "$H" $BASE/states/automation.despertar_suave | python3 -c 'import json,sys; print("estado:", json.load(sys.stdin)["state"])'
# disparo saltando condiciones (verifica que la ACCIÓN funciona; la TV debe encender y ir a Flow 14)
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"automation.despertar_suave","skip_condition":true}' $BASE/services/automation/trigger
```
Expected: `estado: on`; a los ~50s la TV del dormitorio queda en Flow, canal 14 (verificar mirando la TV, o `curl .../states/media_player.tv_dormitorio` → `app_id` = `fCCrJTSe28.Flow`).

---

### Task 3: Modo pasear al perro

**Files:**
- Modify: `homeassistant/scripts.yaml`
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar el script de inicio**

Al final de `homeassistant/scripts.yaml`, agregar:

```yaml
iniciar_paseo:
  alias: "Iniciar paseo (perro)"
  icon: mdi:dog-side
  description: "Apaga TVs, arranca el timer de 30 min y notifica. AWAY queda suspendido."
  sequence:
    - action: media_player.turn_off
      target:
        entity_id:
          - media_player.lg_webos_tv_oled55c3psa
          - media_player.tv_dormitorio
      continue_on_error: true
    - action: timer.start
      target:
        entity_id: timer.paseo
    - action: notify.mobile_app_lucass_iphone
      data:
        title: "🐕 Paseo"
        message: "Modo paseo activo — AWAY suspendido 30 min."
```

- [ ] **Step 2: Agregar las automatizaciones de inicio y fin**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: modo_paseo_inicio
  alias: "Modo paseo: inicio"
  description: "Al encender el switch modo_paseo, ejecuta las acciones de inicio."
  triggers:
    - trigger: state
      entity_id: input_boolean.modo_paseo
      to: "on"
  actions:
    - action: script.iniciar_paseo

- id: modo_paseo_fin
  alias: "Modo paseo: fin"
  description: "El timer llegó a 30 min o Lucas volvió a casa: se apaga el modo paseo."
  triggers:
    - trigger: event
      event_type: timer.finished
      event_data:
        entity_id: timer.paseo
    - trigger: state
      entity_id: person.lucas
      to: "home"
  conditions:
    - condition: state
      entity_id: input_boolean.modo_paseo
      state: "on"
  actions:
    - action: timer.cancel
      target:
        entity_id: timer.paseo
    - action: input_boolean.turn_off
      target:
        entity_id: input_boolean.modo_paseo
```

- [ ] **Step 3: Agregar la condición `not modo_paseo` a `house_mode_salida`**

En `homeassistant/automations.yaml`, en la automatización `house_mode_salida`, el bloque `conditions:` actual es:

```yaml
  conditions:
    - condition: not
      conditions:
        - condition: state
          entity_id: input_select.house_mode
          state: "CLEANING"
```

Reemplazarlo por (agrega el chequeo de modo_paseo):

```yaml
  conditions:
    - condition: not
      conditions:
        - condition: state
          entity_id: input_select.house_mode
          state: "CLEANING"
    - condition: state
      entity_id: input_boolean.modo_paseo
      state: "off"
```

- [ ] **Step 4: Validar y desplegar**

```bash
git add homeassistant/scripts.yaml homeassistant/automations.yaml && git commit -m "feat: modo pasear al perro (suspende AWAY 30 min)"
git push && deploy && checkcfg && reload_script && reload_auto
```
Expected: `check_config` sin ERROR.

- [ ] **Step 5: Verificar el ciclo completo**

```bash
# activar (simula Siri/dashboard)
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"input_boolean.modo_paseo"}' $BASE/services/input_boolean/turn_on >/dev/null
sleep 5
curl -sS -m 5 -H "$H" $BASE/states/timer.paseo | python3 -c 'import json,sys; print("timer:", json.load(sys.stdin)["state"])'
# volver a casa apaga el modo (simula geofence)
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"person.lucas","state":"home"}' $BASE/states/person.lucas >/dev/null
sleep 3
curl -sS -m 5 -H "$H" $BASE/states/input_boolean.modo_paseo | python3 -c 'import json,sys; print("modo_paseo:", json.load(sys.stdin)["state"])'
curl -sS -m 5 -H "$H" $BASE/states/timer.paseo | python3 -c 'import json,sys; print("timer:", json.load(sys.stdin)["state"])'
```
Expected: tras activar, `timer: active` + llega la notif "🐕 Paseo"; tras el `home`, `modo_paseo: off` y `timer: idle`.
Nota: el POST a `/states/person.lucas` es un override temporal para el test; el device_tracker real lo revierte en la próxima actualización. No afecta producción.

---

### Task 4: Aviso TV prendida + AWAY

**Files:**
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar la automatización de aviso y su handler**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: aviso_tv_away
  alias: "Aviso: TV prendida sin nadie"
  description: "Estando AWAY, si una TV queda encendida 2 min, notif accionable con botón Apagar."
  triggers:
    - trigger: state
      entity_id:
        - media_player.lg_webos_tv_oled55c3psa
        - media_player.tv_dormitorio
      to: "on"
      for: "00:02:00"
  conditions:
    - condition: state
      entity_id: input_select.house_mode
      state: "AWAY"
    - condition: state
      entity_id: input_boolean.modo_simulacion
      state: "off"
  actions:
    - action: notify.mobile_app_lucass_iphone
      data:
        title: "📺 TV encendida sin nadie en casa"
        message: "Quedó una TV prendida y estás fuera."
        data:
          actions:
            - action: "APAGAR_TVS"
              title: "Apagar"

- id: aviso_tv_apagar
  alias: "Aviso TV: acción Apagar"
  description: "Responde al botón Apagar de la notificación accionable."
  triggers:
    - trigger: event
      event_type: mobile_app_notification_action
      event_data:
        action: "APAGAR_TVS"
  actions:
    - action: media_player.turn_off
      target:
        entity_id:
          - media_player.lg_webos_tv_oled55c3psa
          - media_player.tv_dormitorio
      continue_on_error: true
```

- [ ] **Step 2: Validar y desplegar**

```bash
git add homeassistant/automations.yaml && git commit -m "feat: aviso accionable de TV prendida estando AWAY"
git push && deploy && checkcfg && reload_auto
```
Expected: `check_config` sin ERROR.

- [ ] **Step 3: Verificar que dispara la notificación**

```bash
# forzar el disparo saltando condiciones y el 'for' (verifica la acción de notif)
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"automation.aviso_tv_away","skip_condition":true}' $BASE/services/automation/trigger
```
Expected: llega al iPhone la notif "📺 TV encendida sin nadie en casa" con botón **Apagar**; tocar el botón apaga ambas TVs (verifica el handler `aviso_tv_apagar`).

---

### Task 5: Presencia simulada (anti-robo)

**Files:**
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar toggle y fin**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: simulacion_toggle
  alias: "Simulación: toggle TV living"
  description: "Con modo_simulacion + AWAY, 19:00-23:30, cada 30 min 50% de togglear el LG."
  triggers:
    - trigger: time_pattern
      minutes: "/30"
  conditions:
    - condition: state
      entity_id: input_boolean.modo_simulacion
      state: "on"
    - condition: state
      entity_id: input_select.house_mode
      state: "AWAY"
    - condition: time
      after: "19:00:00"
      before: "23:30:00"
    - condition: template
      value_template: "{{ range(0, 2) | random == 1 }}"
  actions:
    - action: media_player.toggle
      target:
        entity_id: media_player.lg_webos_tv_oled55c3psa

- id: simulacion_fin
  alias: "Simulación: apagar a las 23:30"
  description: "Cierra la ventana nocturna: apaga el LG si el modo simulación sigue activo."
  triggers:
    - trigger: time
      at: "23:30:00"
  conditions:
    - condition: state
      entity_id: input_boolean.modo_simulacion
      state: "on"
  actions:
    - action: media_player.turn_off
      target:
        entity_id: media_player.lg_webos_tv_oled55c3psa
      continue_on_error: true
```

- [ ] **Step 2: Validar y desplegar**

```bash
git add homeassistant/automations.yaml && git commit -m "feat: presencia simulada anti-robo (modo simulación)"
git push && deploy && checkcfg && reload_auto
```
Expected: `check_config` sin ERROR.

- [ ] **Step 3: Verificar el toggle**

```bash
curl -sS -m 5 -H "$H" $BASE/states/media_player.lg_webos_tv_oled55c3psa | python3 -c 'import json,sys; print("LG antes:", json.load(sys.stdin)["state"])'
# disparo forzado saltando condiciones (incluye el random): la TV debe cambiar de estado
curl -sS -m 10 -X POST -H "$H" -H "Content-Type: application/json" -d '{"entity_id":"automation.simulacion_toggle","skip_condition":true}' $BASE/services/automation/trigger
sleep 8
curl -sS -m 5 -H "$H" $BASE/states/media_player.lg_webos_tv_oled55c3psa | python3 -c 'import json,sys; print("LG después:", json.load(sys.stdin)["state"])'
```
Expected: el estado del LG cambia (off→on u on→off). Nota: con `skip_condition:true` se saltea también el random, así que el toggle siempre ocurre — es el comportamiento correcto para el test.

---

### Task 6: Actualizar documentación

**Files:**
- Modify: `docs/estado-actual.md`

- [ ] **Step 1: Agregar helpers a la sección "Entidades y helpers clave"**

En `docs/estado-actual.md`, después de la línea de `person.lucas`, agregar:

```markdown
- `input_boolean.modo_paseo` — paseo del perro; suspende AWAY 30 min (timer `timer.paseo`)
- `input_boolean.modo_simulacion` — "modo vacío" anti-robo; expuestos ambos a Siri (HomeKit)
```

- [ ] **Step 2: Agregar las automatizaciones nuevas a la tabla de Automatizaciones**

En `docs/estado-actual.md`, en la tabla de la sección "Automatizaciones", agregar filas:

```markdown
| `despertar_suave` | 08:30 L-V en casa → TV dormitorio en Flow canal 14 |
| `modo_paseo_inicio` / `modo_paseo_fin` | Paseo del perro: apaga TVs + timer 30 min; suspende AWAY; se cierra por timer o al volver a home |
| `aviso_tv_away` / `aviso_tv_apagar` | Estando AWAY con TV encendida 2 min → notif accionable con botón Apagar |
| `simulacion_toggle` / `simulacion_fin` | Modo simulación + AWAY, 19-23:30: togglea el LG al azar; apaga a las 23:30 |
```

- [ ] **Step 3: Agregar el script `iniciar_paseo` a la tabla de scripts (sección Dormitorio o una fila general)**

En `docs/estado-actual.md`, tabla de Scripts, agregar bajo Sala o en una nueva fila:

```markdown
| `iniciar_paseo` | Apaga ambas TVs, arranca `timer.paseo` (30 min) y notifica; lo dispara `modo_paseo_inicio` |
```

- [ ] **Step 4: Commit**

```bash
git add docs/estado-actual.md && git commit -m "docs: automatizaciones de software puro en estado-actual"
git push
```

---

## Self-review (cobertura de la spec)

- Helpers (input_boolean × 2 + timer) + HomeKit → **Task 1** ✓
- Despertar suave (08:30 L-V, home, Flow 14) → **Task 2** ✓
- Modo paseo (script + inicio + fin + condición a house_mode_salida) → **Task 3** ✓
- Aviso TV+AWAY (accionable + handler + `not modo_simulacion`) → **Task 4** ✓
- Presencia simulada (toggle 50% en franja + fin 23:30) → **Task 5** ✓
- Interdependencias: `house_mode_salida` gana `not modo_paseo` (Task 3 Step 3); aviso gana `not modo_simulacion` (Task 4) ✓
- Doc actualizada → **Task 6** ✓
