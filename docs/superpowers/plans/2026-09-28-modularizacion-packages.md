# Modularización en packages de HA — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar la config monolítica de HA en packages por feature (tv, house_mode, paseo, seguridad, face, salud), sin cambiar comportamiento. Según `docs/superpowers/specs/2026-09-28-modularizacion-packages-design.md`.

**Architecture:** Se activa `packages: !include_dir_named packages/` en `configuration.yaml`. Cada feature migra a `homeassistant/packages/<feature>.yaml` **moviendo los bloques literales** (mismos `id`/nombres → nada aguas abajo cambia). `automations.yaml`/`scripts.yaml` quedan vacíos pero se mantienen sus `!include` (inocuos, evitan cualquier conflicto de keys — más seguro que eliminarlos).

**Tech Stack:** Home Assistant packages (YAML), `check_config`, API REST de HA.

**Regla de oro:** es un refactor de MOVIMIENTO. Nunca reescribir un bloque de memoria — **cortar y pegar el texto exacto** del archivo origen. Cambiar comportamiento está fuera de alcance.

**Verificación transversal:** `check_config` valida el merge completo de packages SIN reiniciar. El restart va una sola vez al final. Se compara el conjunto de entidades antes/después.

```bash
# helpers
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
checkcfg() { ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull -q
docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -3
EOF
}
```

---

### Task 1: Baseline + activar packages + `packages/tv.yaml`

**Files:**
- Modify: `homeassistant/configuration.yaml`
- Create: `homeassistant/packages/tv.yaml`
- Modify: `homeassistant/automations.yaml`, `homeassistant/scripts.yaml`

- [ ] **Step 1: Capturar el baseline (para comparar al final)**

```bash
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
d=json.load(sys.stdin)
for pref in ("automation.","script.","input_boolean.","input_select.","timer.","switch."):
    ents=sorted(e["entity_id"] for e in d if e["entity_id"].startswith(pref))
    print(pref, len(ents))
    for e in ents: print("  ", e)
' | tee /tmp/ha_baseline.txt
```
Expected: se guarda la lista actual. Anotar los conteos (automation, script, input_boolean, input_select, timer, switch).

- [ ] **Step 2: Activar packages en `configuration.yaml`**

En `homeassistant/configuration.yaml`, en el bloque `homeassistant:`, agregar la línea `packages:` (después de `internal_url`):

```yaml
homeassistant:
  name: Depto
  time_zone: America/Argentina/Buenos_Aires
  unit_system: metric
  currency: ARS
  country: AR
  external_url: "https://ha-mcp.neuralcore.dev"
  internal_url: "http://192.168.1.17:8123"
  packages: !include_dir_named packages/
```

- [ ] **Step 3: Crear `homeassistant/packages/tv.yaml` moviendo los bloques de TV**

Mover (cortar del origen, pegar acá) **el texto literal** de estos elementos:
- Desde `configuration.yaml`: el bloque `wake_on_lan:`, el bloque `template:` (los 6 switches), y el bloque `rest_command:` (`st_tv_dormitorio_app`).
- Desde `scripts.yaml`: `tv_living_encender`, `tv_dormitorio_encender`, `tv_app`, `flow_canal`, `flow_sala`, `netflix_sala`, `youtube_sala`, `tv_app_dormitorio`, `flow_dormitorio`, `netflix_dormitorio`, `youtube_dormitorio`, `flow_canal_dormitorio`.
- Desde `automations.yaml`: `tv_living_wol`, `webhook_flow_sala`, `webhook_netflix_sala`, `webhook_youtube_sala`, `homekit_remote_lg`.

Estructura del package (las keys de dominio agrupan lo movido):
```yaml
# Package TV: control de las dos TVs (LG webOS + Samsung Tizen), apps y canales Flow.
wake_on_lan:

template:
  - switch:
      # ... (los 6 switches movidos textualmente desde configuration.yaml)

rest_command:
  st_tv_dormitorio_app:
    # ... (movido textualmente)

script:
  tv_living_encender:
    # ... (movidos textualmente desde scripts.yaml)
  # tv_dormitorio_encender, tv_app, flow_canal, flow_sala, netflix_sala, youtube_sala,
  # tv_app_dormitorio, flow_dormitorio, netflix_dormitorio, youtube_dormitorio, flow_canal_dormitorio

automation:
  - id: tv_living_wol
    # ... (movidos textualmente desde automations.yaml)
  # webhook_flow_sala, webhook_netflix_sala, webhook_youtube_sala, homekit_remote_lg
```
Nota: en `scripts.yaml` los scripts están como top-level (sin la key `script:`); dentro del package van **bajo `script:`**. En `automations.yaml` son una lista top-level; dentro del package van **bajo `automation:`** (lista con `- id: ...`).

- [ ] **Step 4: Quitar del origen lo movido**

En `configuration.yaml`: borrar los bloques `wake_on_lan:`, `template:` y `rest_command:` (ya están en tv.yaml).
En `scripts.yaml`: borrar los 12 scripts movidos.
En `automations.yaml`: borrar las 5 automatizaciones movidas.

- [ ] **Step 5: Validar y commit**

```bash
git add homeassistant/configuration.yaml homeassistant/packages/tv.yaml homeassistant/scripts.yaml homeassistant/automations.yaml
git commit -m "refactor: package tv (mueve TVs/apps/canales a packages/tv.yaml)"
git push
```
Luego `checkcfg` (pull + check_config sin restart).
Expected: `check_config` termina sin líneas de ERROR (valida el merge de packages).

---

### Task 2: `packages/house_mode.yaml`

**Files:**
- Create: `homeassistant/packages/house_mode.yaml`
- Modify: `homeassistant/configuration.yaml`, `homeassistant/automations.yaml`

- [ ] **Step 1: Crear `packages/house_mode.yaml` moviendo los bloques**

Mover textualmente:
- Desde `configuration.yaml`: el bloque `input_select:` (`house_mode`).
- Desde `automations.yaml`: `house_mode_llegada`, `house_mode_salida`, `house_mode_noche`, `house_mode_manana`, `despertar_suave`.

Estructura:
```yaml
# Package house_mode: estados globales de la casa y rutinas de modo.
input_select:
  house_mode:
    # ... (movido textualmente)

automation:
  - id: house_mode_llegada
    # ... (5 automatizaciones movidas textualmente)
```

- [ ] **Step 2: Quitar del origen**

Borrar el `input_select:` de `configuration.yaml` y las 5 automatizaciones de `automations.yaml`.

- [ ] **Step 3: Validar y commit**

```bash
git add homeassistant/packages/house_mode.yaml homeassistant/configuration.yaml homeassistant/automations.yaml
git commit -m "refactor: package house_mode"
git push
```
Luego `checkcfg`. Expected: sin ERROR.

---

### Task 3: `packages/paseo.yaml`

**Files:**
- Create: `homeassistant/packages/paseo.yaml`
- Modify: `homeassistant/configuration.yaml`, `homeassistant/scripts.yaml`, `homeassistant/automations.yaml`

- [ ] **Step 1: Crear `packages/paseo.yaml` moviendo los bloques**

Mover textualmente:
- Desde `configuration.yaml`: la entrada `modo_paseo` del bloque `input_boolean:` y el bloque `timer:` (`paseo`).
- Desde `scripts.yaml`: `iniciar_paseo`.
- Desde `automations.yaml`: `modo_paseo_inicio`, `modo_paseo_fin`.

Estructura:
```yaml
# Package paseo: modo pasear al perro (suspende AWAY 30 min).
input_boolean:
  modo_paseo:
    name: Modo paseo
    icon: mdi:dog-side

timer:
  paseo:
    # ... (movido textualmente)

script:
  iniciar_paseo:
    # ... (movido textualmente)

automation:
  - id: modo_paseo_inicio
    # ...
  - id: modo_paseo_fin
    # ...
```
Nota: `input_boolean:` aparecerá en varios packages (paseo, seguridad, face); HA mergea las entradas. Cada package declara **solo su** entrada.

- [ ] **Step 2: Quitar del origen**

De `configuration.yaml`: quitar la entrada `modo_paseo` del `input_boolean:` y todo el bloque `timer:`. De `scripts.yaml`: `iniciar_paseo`. De `automations.yaml`: las 2 automatizaciones.

- [ ] **Step 3: Validar y commit**

```bash
git add homeassistant/packages/paseo.yaml homeassistant/configuration.yaml homeassistant/scripts.yaml homeassistant/automations.yaml
git commit -m "refactor: package paseo"
git push
```
Luego `checkcfg`. Expected: sin ERROR.

---

### Task 4: `packages/seguridad.yaml`

**Files:**
- Create: `homeassistant/packages/seguridad.yaml`
- Modify: `homeassistant/configuration.yaml`, `homeassistant/automations.yaml`

- [ ] **Step 1: Crear `packages/seguridad.yaml` moviendo los bloques**

Mover textualmente:
- Desde `configuration.yaml`: la entrada `modo_simulacion` del `input_boolean:`.
- Desde `automations.yaml`: `simulacion_toggle`, `simulacion_fin`, `aviso_tv_away`, `aviso_tv_apagar`.

Estructura:
```yaml
# Package seguridad: presencia simulada anti-robo + aviso de TV encendida sin nadie.
input_boolean:
  modo_simulacion:
    name: Modo simulación (anti-robo)
    icon: mdi:shield-home

automation:
  - id: simulacion_toggle
    # ... (4 automatizaciones movidas textualmente)
```

- [ ] **Step 2: Quitar del origen**

De `configuration.yaml`: quitar la entrada `modo_simulacion`. De `automations.yaml`: las 4 automatizaciones.

- [ ] **Step 3: Validar y commit**

```bash
git add homeassistant/packages/seguridad.yaml homeassistant/configuration.yaml homeassistant/automations.yaml
git commit -m "refactor: package seguridad"
git push
```
Luego `checkcfg`. Expected: sin ERROR.

---

### Task 5: `packages/face.yaml`

**Files:**
- Create: `homeassistant/packages/face.yaml`
- Modify: `homeassistant/configuration.yaml`, `homeassistant/automations.yaml`

- [ ] **Step 1: Crear `packages/face.yaml` moviendo los bloques**

Mover textualmente:
- Desde `configuration.yaml`: la entrada `lucas_visto_camara` del `input_boolean:` (con esto el bloque `input_boolean:` de configuration.yaml queda vacío → eliminarlo entero).
- Desde `automations.yaml`: `face_reconocido`, `face_lucas_presencia`.

Estructura:
```yaml
# Package face: reconocimiento facial → señal blanda + notificaciones.
input_boolean:
  lucas_visto_camara:
    name: Lucas visto por cámara
    icon: mdi:face-recognition

automation:
  - id: face_reconocido
    # ...
  - id: face_lucas_presencia
    # ...
```

- [ ] **Step 2: Quitar del origen**

De `configuration.yaml`: quitar la entrada `lucas_visto_camara` y, si el `input_boolean:` quedó sin entradas, borrar la key entera. De `automations.yaml`: las 2 automatizaciones.

- [ ] **Step 3: Validar y commit**

```bash
git add homeassistant/packages/face.yaml homeassistant/configuration.yaml homeassistant/automations.yaml
git commit -m "refactor: package face"
git push
```
Luego `checkcfg`. Expected: sin ERROR.

---

### Task 6: `packages/salud.yaml`

**Files:**
- Create: `homeassistant/packages/salud.yaml`
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Crear `packages/salud.yaml` moviendo la automatización**

Mover textualmente desde `automations.yaml`: `salud_alerta`.

Estructura:
```yaml
# Package salud: alerta de servicios caídos (observabilidad).
automation:
  - id: salud_alerta
    # ... (movido textualmente)
```

- [ ] **Step 2: Quitar del origen**

De `automations.yaml`: `salud_alerta`. En este punto `automations.yaml` y `scripts.yaml` deberían quedar vacíos.

- [ ] **Step 3: Dejar los monolitos vacíos**

Asegurar que `homeassistant/automations.yaml` contiene solo `[]` y `homeassistant/scripts.yaml` solo `{}` (se mantienen los `!include` en configuration.yaml apuntando a estos archivos vacíos — inocuo y seguro).

```bash
echo '[]' > homeassistant/automations.yaml
echo '{}' > homeassistant/scripts.yaml
```

- [ ] **Step 4: Validar y commit**

```bash
git add homeassistant/packages/salud.yaml homeassistant/automations.yaml homeassistant/scripts.yaml
git commit -m "refactor: package salud + vaciar monolitos"
git push
```
Luego `checkcfg`. Expected: sin ERROR.

---

### Task 7: Aplicar (restart) y verificar equivalencia

**Files:** ninguno.

- [ ] **Step 1: Restart de HA**

```bash
ssh r2130 'docker restart homeassistant' && sleep 45
curl -sS -m 5 -o /dev/null -w "HA: %{http_code}\n" http://192.168.1.17:8123
```
Expected: HA responde (200/302).

- [ ] **Step 2: Comparar el conjunto de entidades con el baseline**

```bash
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
d=json.load(sys.stdin)
for pref in ("automation.","script.","input_boolean.","input_select.","timer.","switch."):
    ents=sorted(e["entity_id"] for e in d if e["entity_id"].startswith(pref))
    print(pref, len(ents))
    for e in ents: print("  ", e)
' > /tmp/ha_after.txt
diff /tmp/ha_baseline.txt /tmp/ha_after.txt && echo "IDÉNTICO ✓" || echo "HAY DIFERENCIAS (revisar)"
```
Expected: `IDÉNTICO ✓` (mismo conjunto de automatizaciones, scripts, helpers y switches; nada de menos ni duplicado).

- [ ] **Step 3: Prueba funcional**

```bash
# un script (Flow canal por nombre) y una automatización siguen operativos
curl -sS -m 5 -H "$H" $BASE/states/automation.salud_alerta_de_servicio | python3 -c 'import json,sys; print("salud_alerta:", json.load(sys.stdin)["state"])'
curl -sS -m 5 -H "$H" $BASE/states/script.flow_canal | python3 -c 'import json,sys; print("flow_canal:", json.load(sys.stdin)["state"])'
```
Expected: ambas existen y en estado válido (`on`/`off`). Los logs de HA sin errores de config:
```bash
ssh r2130 'docker logs homeassistant --since 2m 2>&1 | grep -iE "error|invalid|package" | grep -v habluetooth | head'
```
Expected: sin errores de packages/config.

---

### Task 8: Documentación

**Files:**
- Modify: `docs/estado-actual.md`, `docs/runbooks/pendientes.md`, `README.md`

- [ ] **Step 1: Actualizar la estructura del repo en `README.md` y `estado-actual.md`**

En la sección de estructura del repo (README.md), reemplazar la descripción de `homeassistant/` para reflejar los packages:
```markdown
│   ├── configuration.yaml    → core: default_config, http, homeassistant+packages, homekit, lovelace
│   ├── packages/             → config por feature (tv, house_mode, paseo, seguridad, face, salud)
│   ├── automations.yaml / scripts.yaml → vacíos (todo migró a packages; se mantiene el !include)
│   ├── dashboards/remoto.yaml
│   └── secrets.yaml (fuera de git)
```

- [ ] **Step 2: Marcar el sub-proyecto en `pendientes.md`**

En "Refactor de arquitectura", mover Modularización a HECHO:
```markdown
- HECHO 2026-09-28: **Modularización** — config de HA reorganizada en `packages/` por feature
  (tv, house_mode, paseo, seguridad, face, salud). automations.yaml/scripts.yaml vacíos.
- PENDIENTE: **Parametrización** — valores casa-específicos a secrets.yaml + compose profiles +
  doc onboarding (ahora sobre la base modular, más fácil).
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/estado-actual.md docs/runbooks/pendientes.md
git commit -m "docs: modularización en packages"
git push
```

---

## Self-review (cobertura de la spec)

- `packages: !include_dir_named` en configuration.yaml → **Task 1 Step 2** ✓
- 6 packages con el mapeo exacto de la spec → **Tasks 1–6** ✓ (tv: 5 autom + 12 scripts + wake_on_lan/template/rest_command; house_mode: 5 autom + input_select; paseo: 2 autom + input_boolean/timer/script; seguridad: 4 autom + input_boolean; face: 2 autom + input_boolean; salud: 1 autom) → total 19 automatizaciones, 13 scripts ✓
- Monolitos vacíos, `!include` mantenidos (más seguro que eliminarlos) → **Task 6 Step 3** ✓
- homekit/lovelace/http quedan en core → no se tocan (Tasks solo mueven lo mapeado) ✓
- Verificación incremental (`check_config` por task) + equivalencia final (diff baseline) → **cada task + Task 7** ✓
- Refactor de movimiento (no reescribir) → nota "Regla de oro" + instrucción "mover textualmente" en cada task ✓
- Docs → **Task 8** ✓
- Nota: conteo esperado = 19 automatizaciones + 13 scripts + 3 input_boolean + 1 input_select + 1 timer + 6 switches (baseline en Task 1 lo fija).
