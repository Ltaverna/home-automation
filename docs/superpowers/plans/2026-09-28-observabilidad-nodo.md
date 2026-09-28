# Observabilidad de nodo — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar métricas del host R2130 (CPU/RAM/temp/NVMe/Hailo) como sensores en HA por MQTT Discovery, con alertas accionables y en la vista Salud. Según `docs/superpowers/specs/2026-09-28-observabilidad-nodo-design.md`.

**Architecture:** `scripts/node-metrics.sh` en el host (cron 1 min) lee métricas con comandos del host y publica a MQTT vía `docker exec mosquitto mosquitto_pub`; HA crea los sensores por Discovery. Alertas en `packages/salud.yaml`; métricas en la vista "Salud".

**Tech Stack:** bash, /proc + /sys, smartctl, hailortcli, MQTT Discovery, HA.

**Notas de entorno:** el script corre como root en la R2130 (necesita thermal/smartctl/hailo/docker). Publica con las credenciales MQTT del `.env`. Comandos de deploy: editar en el mini-PC → push → `git pull` en la R2130 (con `cd`, ojo).

```bash
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
```

---

### Task 1: Reconocimiento — confirmar comandos del host

**Files:** ninguno (exploración; sus resultados fijan detalles del script).

- [ ] **Step 1: Verificar cada fuente de métrica en la R2130**

```bash
ssh r2130 'bash -s' <<'EOF'
echo "=== temp CPU (thermal) ==="; cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "no thermal_zone0"
echo "=== disco / ==="; df -P / | tail -1 | awk '{print $5}'
echo "=== meminfo ==="; grep -E 'MemTotal|MemAvailable' /proc/meminfo
echo "=== smartctl ==="; command -v smartctl >/dev/null && sudo smartctl -H /dev/nvme0 2>&1 | grep -iE "result|health" || echo "smartmontools NO instalado"
echo "=== hailo temp/util (probar subcomandos) ==="
hailortcli fw-control identify 2>&1 | grep -iE "temp" || echo "identify sin temp"
hailortcli monitor --help 2>&1 | head -3 || echo "sin monitor"
hailortcli measure-power --help 2>&1 | head -3 || echo "sin measure-power"
EOF
```
Expected: se ve el valor de thermal (miligrados, ej. `52000`), el `%` de disco, MemTotal/MemAvailable. Anotar: si `smartctl` falta (se instala en Task 2) y **qué subcomando de `hailortcli` expone temperatura** (si ninguno lo hace fácil, el sensor Hailo se omite — decisión registrada en la spec).

---

### Task 2: Instalar smartmontools en el host

**Files:** ninguno (setup del host).

- [ ] **Step 1: Instalar**

```bash
ssh r2130 'command -v smartctl >/dev/null && echo "ya instalado" || (sudo apt-get update -qq && sudo apt-get install -y smartmontools && echo instalado)'
```
Expected: `smartctl` disponible.

- [ ] **Step 2: Probar SMART del NVMe**

```bash
ssh r2130 'sudo smartctl -H /dev/nvme0 2>&1 | grep -iE "result|health"'
```
Expected: una línea tipo `SMART overall-health self-assessment test result: PASSED`.

---

### Task 3: Script `scripts/node-metrics.sh`

**Files:**
- Create: `scripts/node-metrics.sh`

- [ ] **Step 1: Escribir `scripts/node-metrics.sh`**

Ajustar en el Step tras la Task 1 el bloque Hailo según el subcomando real (o dejar el sensor
Hailo comentado si no está disponible). Contenido base:

```bash
#!/usr/bin/env bash
# Métricas del host R2130 → MQTT Discovery (sensores en HA). Corre por cron como root.
set -uo pipefail

ENV_FILE=/opt/home-automation/.env
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
MQTT_USER="${MQTT_USER:-ha}"; MQTT_PASSWORD="${MQTT_PASSWORD:-}"

pub() {  # pub <topic> <payload> [retain]
  local topic="$1" payload="$2" retain="${3:-}"
  docker exec mosquitto mosquitto_pub -u "$MQTT_USER" -P "$MQTT_PASSWORD" \
    -t "$topic" -m "$payload" ${retain:+-r} 2>/dev/null || true
}

discovery() {  # discovery <key> <name> <device_class|""> <unit|""> [binary]
  local key="$1" name="$2" dclass="$3" unit="$4" kind="${5:-sensor}"
  local cfg="{\"name\":\"$name\",\"unique_id\":\"node_$key\",\"state_topic\":\"depto/nodo/$key\","
  cfg+="\"device\":{\"identifiers\":[\"r2130_node\"],\"name\":\"Nodo R2130\"}"
  [ -n "$dclass" ] && cfg+=",\"device_class\":\"$dclass\""
  [ -n "$unit" ] && cfg+=",\"unit_of_measurement\":\"$unit\""
  [ "$kind" = "binary_sensor" ] && cfg+=",\"payload_on\":\"ON\",\"payload_off\":\"OFF\""
  cfg+="}"
  pub "homeassistant/$kind/node_$key/config" "$cfg" retain
}

# --- Discovery (retained) ---
discovery cpu "Nodo CPU" "" "%"
discovery ram "Nodo RAM" "" "%"
discovery temp_cpu "Nodo Temp CPU" temperature "°C"
discovery disk "Nodo Disco NVMe" "" "%"
discovery nvme_smart "Nodo SMART NVMe" problem "" binary_sensor

# --- CPU % (delta de /proc/stat en 1s) ---
read_cpu() { awk '/^cpu /{t=$2+$3+$4+$5+$6+$7+$8; i=$5; print t, i}' /proc/stat; }
r1=$(read_cpu); sleep 1; r2=$(read_cpu)
cpu=$(awk -v a="$r1" -v b="$r2" 'BEGIN{split(a,x," ");split(b,y," ");dt=y[1]-x[1];di=y[2]-x[2]; if(dt>0) printf "%.0f", (1-di/dt)*100; else print 0}')
pub depto/nodo/cpu "$cpu"

# --- RAM % ---
ram=$(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "%.0f",(1-a/t)*100}' /proc/meminfo)
pub depto/nodo/ram "$ram"

# --- Temp CPU (°C) ---
if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
  tc=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
  pub depto/nodo/temp_cpu "$tc"
fi

# --- Disco / (%) ---
disk=$(df -P / | tail -1 | awk '{gsub("%","",$5); print $5}')
pub depto/nodo/disk "$disk"

# --- SMART NVMe (PASSED → OFF / else ON) ---
if command -v smartctl >/dev/null; then
  if smartctl -H /dev/nvme0 2>/dev/null | grep -qi "PASSED"; then
    pub depto/nodo/nvme_smart "OFF"
  else
    pub depto/nodo/nvme_smart "ON"
  fi
fi

# --- Temp Hailo (opcional; se completa en Task 1 con el subcomando real) ---
# Placeholder: si hay un comando confiable, descomentar y publicar depto/nodo/hailo_temp
#   discovery hailo_temp "Nodo Temp Hailo" temperature "°C"   # (mover arriba con los otros discovery)
#   ht=$(hailortcli ... )
#   pub depto/nodo/hailo_temp "$ht"

echo "node-metrics OK: $(date -Is) cpu=$cpu ram=$ram disk=$disk"
```

- [ ] **Step 2: Ajustar el bloque Hailo según Task 1**

Si la Task 1 encontró un subcomando de `hailortcli` que da temperatura, agregar `discovery hailo_temp "Nodo Temp Hailo" temperature "°C"` junto a los otros discovery y el `pub depto/nodo/hailo_temp "$ht"` con el comando real. Si no, dejar el bloque comentado (documentar en el commit que el sensor Hailo queda pendiente).

- [ ] **Step 3: Permisos, sintaxis, commit**

```bash
bash -n scripts/node-metrics.sh && echo "sintaxis OK"
chmod +x scripts/node-metrics.sh
git add scripts/node-metrics.sh
git commit -m "feat: node-metrics.sh (métricas host → MQTT Discovery)"
git push
```

---

### Task 4: Primera corrida + verificar sensores en HA

**Files:** ninguno.

- [ ] **Step 1: Correr el script en la R2130**

```bash
ssh r2130 'cd /opt/home-automation && git pull -q && sudo ./scripts/node-metrics.sh'
```
Expected: `node-metrics OK: <fecha> cpu=.. ram=.. disk=..`.

- [ ] **Step 2: Verificar los sensores en HA**

```bash
sleep 5
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
for e in json.load(sys.stdin):
    if e["entity_id"].startswith(("sensor.node_","binary_sensor.node_")):
        print(" ", e["entity_id"], "=", e["state"], e["attributes"].get("unit_of_measurement",""))'
```
Expected: `sensor.node_cpu`, `node_ram`, `node_temp_cpu`, `node_disk` con valores numéricos y
`binary_sensor.node_nvme_smart = off` (SMART PASSED). (Hailo si se incluyó en Task 3.)

---

### Task 5: Cron

**Files:** ninguno (crontab root).

- [ ] **Step 1: Instalar el cron (cada 1 min)**

```bash
ssh r2130 '(sudo crontab -l 2>/dev/null | grep -v node-metrics.sh; echo "* * * * * /opt/home-automation/scripts/node-metrics.sh >> /var/log/node-metrics.log 2>&1") | sudo crontab -'
ssh r2130 'sudo crontab -l | grep -E "node-metrics|backup"'
```
Expected: se ve la línea `* * * * * ...node-metrics.sh` junto a las de backup.

- [ ] **Step 2: Confirmar refresco automático**

```bash
sleep 75
curl -sS -m 5 -H "$H" $BASE/states/sensor.node_cpu | python3 -c 'import json,sys; d=json.load(sys.stdin); print("node_cpu:", d["state"], "| actualizado:", d["last_updated"][:19])'
```
Expected: `last_updated` de hace <90s (el cron lo refrescó).

---

### Task 6: Alerta `nodo_alerta` en `packages/salud.yaml`

**Files:**
- Modify: `homeassistant/packages/salud.yaml`

- [ ] **Step 1: Agregar la automatización al package salud**

En `homeassistant/packages/salud.yaml`, dentro del bloque `automation:` (después de `salud_alerta`),
agregar:

```yaml
  - id: nodo_alerta
    alias: "Nodo: alerta de recursos"
    description: "Notifica al iPhone ante disco lleno, temperatura crítica o SMART en falla."
    triggers:
      - trigger: numeric_state
        entity_id: sensor.node_disk
        above: 85
        id: disco
      - trigger: numeric_state
        entity_id: sensor.node_temp_cpu
        above: 80
        id: temp_cpu
      - trigger: state
        entity_id: binary_sensor.node_nvme_smart
        to: "on"
        id: smart
    actions:
      - choose:
          - conditions:
              - condition: trigger
                id: disco
            sequence:
              - action: notify.mobile_app_lucass_iphone
                data:
                  title: "⚠️ Disco NVMe casi lleno"
                  message: "Uso del disco: {{ states('sensor.node_disk') }}%."
          - conditions:
              - condition: trigger
                id: temp_cpu
            sequence:
              - action: notify.mobile_app_lucass_iphone
                data:
                  title: "🌡️ CPU caliente"
                  message: "Temp CPU: {{ states('sensor.node_temp_cpu') }}°C."
          - conditions:
              - condition: trigger
                id: smart
            sequence:
              - action: notify.mobile_app_lucass_iphone
                data:
                  title: "💾 SMART del NVMe: FALLA"
                  message: "El NVMe reporta estado de salud no-PASSED. Backup y revisar."
```

Nota: `numeric_state above` dispara al cruzar el umbral (no repite mientras se mantiene) → anti-spam
natural. Si en Task 3 se incluyó `sensor.node_hailo_temp`, agregar un trigger análogo (above: 80,
id: temp_hailo) con su choose.

- [ ] **Step 2: Validar, deploy, reload**

```bash
git add homeassistant/packages/salud.yaml
git commit -m "feat: nodo_alerta (disco/temp/SMART) en package salud"
git push
ssh r2130 'bash -s' <<'EOF'
cd /opt/home-automation && git pull -q
docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -2
EOF
curl -sS -m 10 -X POST -H "$H" $BASE/services/automation/reload >/dev/null && echo "reload ok"
```
Expected: `check_config` sin ERROR; reload ok.

- [ ] **Step 3: Verificar la automatización + probar una alerta**

```bash
curl -sS -m 5 -H "$H" $BASE/states/automation.nodo_alerta_de_recursos | python3 -c 'import json,sys; print("estado:", json.load(sys.stdin)["state"])'
# prueba: disparar manualmente el disco bajando el umbral no es trivial → trigger directo del numeric_state
# via publicar un valor alto de disco temporal:
ssh r2130 'source /opt/home-automation/.env; docker exec mosquitto mosquitto_pub -u "$MQTT_USER" -P "$MQTT_PASSWORD" -t depto/nodo/disk -m 99'
echo "→ debería llegar '⚠️ Disco NVMe casi lleno: 99%' al iPhone"
sleep 5
# restaurar el valor real (el cron lo corrige en <1 min igual)
ssh r2130 '/opt/home-automation/scripts/node-metrics.sh >/dev/null 2>&1 || sudo /opt/home-automation/scripts/node-metrics.sh >/dev/null 2>&1'
```
Expected: `automation.nodo_alerta_de_recursos = on`; llega la notif de disco; el valor real se
restaura en el próximo ciclo. (entity_id se genera del alias → `automation.nodo_alerta_de_recursos`.)

---

### Task 7: Vista "Salud" — agregar métricas de nodo

**Files:**
- Modify: `homeassistant/dashboards/remoto.yaml`

- [ ] **Step 1: Agregar una tarjeta a la vista "Salud"**

En `homeassistant/dashboards/remoto.yaml`, en la vista `Salud` (tras la tarjeta de servicios),
agregar:

```yaml
      - type: entities
        title: Nodo R2130
        entities:
          - entity: sensor.node_cpu
            name: CPU
          - entity: sensor.node_ram
            name: RAM
          - entity: sensor.node_temp_cpu
            name: Temp CPU
          - entity: sensor.node_disk
            name: Disco NVMe
          - entity: binary_sensor.node_nvme_smart
            name: SMART NVMe
```
(Si se incluyó `sensor.node_hailo_temp`, agregarlo también con `name: Temp Hailo`.)

- [ ] **Step 2: Commit, deploy**

```bash
git add homeassistant/dashboards/remoto.yaml
git commit -m "feat: métricas de nodo en la vista Salud"
git push
ssh r2130 'cd /opt/home-automation && git pull -q'
```
Expected: en la app HA, la pestaña "Salud" muestra la tarjeta "Nodo R2130" con las métricas.

---

### Task 8: Documentación (MUST) — cierre del hardening

**Files:**
- Modify: `docs/estado-actual.md`, `docs/runbooks/pendientes.md`, `README.md`

- [ ] **Step 1: `estado-actual.md`**

En integraciones/entidades, agregar:
```markdown
- `node-metrics.sh` (host, cron 1 min): métricas del nodo → MQTT. Sensores `sensor.node_cpu/ram/
  temp_cpu/disk` + `binary_sensor.node_nvme_smart` (device "Nodo R2130"). Alerta `nodo_alerta`.
```

- [ ] **Step 2: `pendientes.md` — cerrar el hardening**

```markdown
3. ~~Observabilidad de nodo~~ HECHO 2026-09-28: `node-metrics.sh` (CPU/RAM/temp/disco/SMART →
   MQTT), vista "Salud", alerta `nodo_alerta`. **Hardening pre-Fase 2 COMPLETO (3/3).**
```

- [ ] **Step 3: `README.md`**

En la fila Hardening del roadmap, marcar observabilidad de nodo ✅ y el bloque como completo.
En servicios, mencionar `node-metrics.sh` (host, métricas del nodo).

- [ ] **Step 4: Commit**

```bash
git add docs/estado-actual.md docs/runbooks/pendientes.md README.md
git commit -m "docs: observabilidad de nodo — hardening pre-Fase 2 completo"
git push
```

---

## Self-review (cobertura de la spec)

- Reconocimiento de comandos + confirmar Hailo → **Task 1** ✓
- smartmontools → **Task 2** ✓
- `node-metrics.sh` (CPU/RAM/temp/disco/SMART, MQTT Discovery, device, try/except) → **Task 3** ✓
- Métrica Hailo condicional (se incluye si hay comando; si no, se omite documentado) → **Task 1 + Task 3 Step 2** ✓
- Primera corrida + sensores en HA → **Task 4** ✓
- Cron 1 min → **Task 5** ✓
- Alerta accionable (disco/temp/SMART, anti-spam por numeric_state) → **Task 6** ✓
- Vista Salud → **Task 7** ✓
- Docs (estado, pendientes, README) + cierre del hardening → **Task 8** ✓
- Publicación vía `docker exec mosquitto` (sin instalar clientes) → **Task 3** ✓
