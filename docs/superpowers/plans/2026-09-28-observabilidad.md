# Observabilidad / salud del sistema — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enterarse si algo del sistema deja de andar: contenedor `healthmon` que hace health-checks HTTP y publica a MQTT (sensores en HA), dashboard de salud, notificación al iPhone, y watchdog externo (healthchecks.io). Según `docs/superpowers/specs/2026-09-28-observabilidad-design.md`.

**Architecture:** `healthmon` (Python) chequea `face-embed`, `ha-mcp` y HA por HTTP cada 60s, publica `binary_sensor` por MQTT Discovery, y si HA está OK pinguea un dead-man switch externo. HA muestra una vista "Salud" y notifica en transiciones.

**Tech Stack:** Python 3.11, requests, paho-mqtt 1.6.1, MQTT Discovery, healthchecks.io.

**Notas de entorno:** `healthmon` corre en la red default de compose → `face-embed:8000` y `mosquitto:1883` por nombre; HA y ha-mcp corren en host-network → se chequean por IP del nodo (`192.168.1.17:8123` y `192.168.1.17:9584`). Secretos (`HEALTHCHECKS_URL`, `MQTT_*`) del `.env`. Deploy: `git pull` en la R2130.

```bash
# helpers de terminal
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
```

---

### Task 1: Script del monitor (`healthmon/monitor.py`)

**Files:**
- Create: `healthmon/monitor.py`

- [ ] **Step 1: Escribir `healthmon/monitor.py`**

```python
#!/usr/bin/env python3
"""Monitor de salud → MQTT + watchdog externo (dead-man switch).
Chequea servicios por HTTP cada INTERVAL s, publica binary_sensor por MQTT Discovery,
y si HA está OK pinguea healthchecks.io. Si HA/Raspi/internet caen, deja de pingar.
"""
import json, os, time, datetime
import requests
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "ha")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
HEALTHCHECKS_URL = os.environ.get("HEALTHCHECKS_URL", "")
INTERVAL = float(os.environ.get("INTERVAL", "60"))

# clave -> (nombre visible, función de check que devuelve (ok: bool, detalle: str))
NODE = os.environ.get("NODE_IP", "192.168.1.17")


def check_http(url, ok_codes=(200, 302), needs=None):
    try:
        r = requests.get(url, timeout=8)
        if r.status_code not in ok_codes:
            return False, f"HTTP {r.status_code}"
        if needs and needs not in r.text:
            return False, "respuesta inesperada"
        return True, "ok"
    except Exception as e:
        return False, repr(e)[:80]


def check_faceembed():
    return check_http("http://face-embed:8000/health", needs='"status"')


def check_mcp():
    # cualquier respuesta HTTP (incluye 404/405) = servicio vivo; sin conexión = caído
    try:
        requests.get(f"http://{NODE}:9584/", timeout=8)
        return True, "ok"
    except Exception as e:
        return False, repr(e)[:80]


def check_ha():
    return check_http(f"http://{NODE}:8123/", ok_codes=(200, 302))


SERVICES = {
    "faceembed": ("Salud face-embed", check_faceembed),
    "mcp": ("Salud MCP", check_mcp),
    "ha": ("Salud Home Assistant", check_ha),
}


def discovery_payload(key, name):
    return {
        "name": name,
        "unique_id": f"salud_{key}",
        "state_topic": f"depto/salud/{key}",
        "json_attributes_topic": f"depto/salud/{key}/attrs",
        "device_class": "problem",
        "payload_on": "ON",
        "payload_off": "OFF",
    }


def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    for key, (name, _) in SERVICES.items():
        topic = f"homeassistant/binary_sensor/salud_{key}/config"
        client.publish(topic, json.dumps(discovery_payload(key, name)), qos=1, retain=True)
    print("healthmon iniciado", flush=True)
    while True:
        ha_ok = False
        for key, (name, fn) in SERVICES.items():
            try:
                ok, detail = fn()
            except Exception as e:
                ok, detail = False, repr(e)[:80]
            if key == "ha":
                ha_ok = ok
            state = "OFF" if ok else "ON"  # device_class problem: ON = problema
            attrs = {"checked": datetime.datetime.now().isoformat(timespec="seconds"), "detail": detail}
            client.publish(f"depto/salud/{key}", state, qos=0, retain=True)
            client.publish(f"depto/salud/{key}/attrs", json.dumps(attrs), qos=0, retain=True)
            print(f"{key}: {'ok' if ok else 'FAIL'} ({detail})", flush=True)
        # dead-man switch: solo pinguear si HA respondió OK
        if ha_ok and HEALTHCHECKS_URL:
            try:
                requests.get(HEALTHCHECKS_URL, timeout=8)
            except Exception as e:
                print("ping healthchecks falló:", repr(e)[:80], flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar sintaxis y commit**

```bash
python3 -m py_compile healthmon/monitor.py && echo OK
git add healthmon/monitor.py
git commit -m "feat: monitor.py de healthmon (health-checks → MQTT + dead-man switch)"
```
Expected: `OK`, commit creado.

---

### Task 2: Dockerfile del `healthmon`

**Files:**
- Create: `healthmon/Dockerfile`

- [ ] **Step 1: Escribir `healthmon/Dockerfile`**

```dockerfile
FROM python:3.11-slim

RUN pip install --no-cache-dir requests==2.31.0 paho-mqtt==1.6.1

COPY monitor.py /app/monitor.py
WORKDIR /app
CMD ["python3", "-u", "monitor.py"]
```

- [ ] **Step 2: Commit**

```bash
git add healthmon/Dockerfile
git commit -m "feat: Dockerfile del healthmon"
```

---

### Task 3: Servicio en compose + `.env.example`

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Agregar el servicio `healthmon`**

En `docker-compose.yml`, después del bloque `face-recognizer` (antes de `cloudflared-mcp`), agregar:

```yaml
  # Monitor de salud: health-checks HTTP → MQTT (sensores en HA) + dead-man switch externo.
  healthmon:
    build: ./healthmon
    container_name: healthmon
    restart: unless-stopped
    environment:
      - TZ=${TZ}
      - MQTT_HOST=mosquitto
      - MQTT_USER=${MQTT_USER}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - HEALTHCHECKS_URL=${HEALTHCHECKS_URL}
      - NODE_IP=192.168.1.17
    depends_on:
      - mosquitto
```

- [ ] **Step 2: Documentar `HEALTHCHECKS_URL` en `.env.example`**

En `.env.example`, agregar al final:

```text
# Watchdog externo (dead-man switch). Crear un check gratis en healthchecks.io y pegar la URL de ping.
HEALTHCHECKS_URL=https://hc-ping.com/REEMPLAZAR-CON-TU-UUID
```

- [ ] **Step 3: Commit, push, agregar el secreto en la R2130, build**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: servicio healthmon en compose + HEALTHCHECKS_URL en .env.example"
git push
# En la R2130: agregar la URL real al .env (el usuario provee la URL de healthchecks.io)
ssh r2130 'cd /opt/home-automation && grep -q HEALTHCHECKS_URL .env || echo "HEALTHCHECKS_URL=<PEGAR_URL>" >> .env'
ssh r2130 'cd /opt/home-automation && git pull -q && docker compose build healthmon 2>&1 | tail -4 && docker compose up -d healthmon'
```
Expected: build OK, contenedor `healthmon` levantado.
Nota: la URL real de healthchecks.io la pega el usuario en `.env` (reemplaza `<PEGAR_URL>`). Si aún no la tiene, el monitor funciona igual (solo no pinguea el watchdog).

- [ ] **Step 4: Verificar que publica salud a MQTT**

```bash
ssh r2130 'docker logs healthmon --since 90s 2>&1 | tail -8'
```
Expected: `healthmon iniciado` y líneas `faceembed: ok (...)`, `mcp: ok`, `ha: ok`.

```bash
ssh r2130 'bash -lc "cd /opt/home-automation && set -a && . ./.env && set +a && docker exec mosquitto mosquitto_sub -u \$MQTT_USER -P \$MQTT_PASSWORD -t depto/salud/# -C 3 -W 10"'
```
Expected: aparecen los estados (`OFF` = ok) de los servicios.

---

### Task 4: Verificar los sensores en HA + probar caída

**Files:** ninguno (HA crea los sensores por Discovery).

- [ ] **Step 1: Confirmar los binary_sensors**

```bash
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
for e in json.load(sys.stdin):
    if e["entity_id"].startswith("binary_sensor.salud"): print(e["entity_id"], "=", e["state"], "|", e["attributes"].get("detail"))'
```
Expected: `binary_sensor.salud_faceembed`, `salud_mcp`, `salud_ha`, todos `off` (device_class problem: off = ok).

- [ ] **Step 2: Probar detección de caída**

Parar `face-embed` y verificar que su sensor pasa a "problema" (on):
```bash
ssh r2130 'cd /opt/home-automation && docker compose stop face-embed'
sleep 70
curl -sS -m 5 -H "$H" $BASE/states/binary_sensor.salud_faceembed | python3 -c 'import json,sys; d=json.load(sys.stdin); print("salud_faceembed:", d["state"], "|", d["attributes"].get("detail"))'
```
Expected: `salud_faceembed: on | <error de conexión>`.

Reactivar:
```bash
ssh r2130 'cd /opt/home-automation && docker compose start face-embed'
sleep 70
curl -sS -m 5 -H "$H" $BASE/states/binary_sensor.salud_faceembed | python3 -c 'import json,sys; print("salud_faceembed:", json.load(sys.stdin)["state"])'
```
Expected: vuelve a `off`.

---

### Task 5: Automatización de notificación `salud_alerta`

**Files:**
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar la automatización**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: salud_alerta
  alias: "Salud: alerta de servicio"
  description: "Notifica al iPhone cuando un servicio no-core cae o se recupera (transición)."
  triggers:
    - trigger: state
      entity_id:
        - binary_sensor.salud_faceembed
        - binary_sensor.salud_mcp
      to: "on"
      id: caido
    - trigger: state
      entity_id:
        - binary_sensor.salud_faceembed
        - binary_sensor.salud_mcp
      to: "off"
      id: recuperado
  conditions:
    - condition: template
      value_template: "{{ trigger.from_state.state not in ['unknown', 'unavailable', None] }}"
  actions:
    - choose:
        - conditions:
            - condition: trigger
              id: caido
          sequence:
            - action: notify.mobile_app_lucass_iphone
              data:
                title: "⚠️ Servicio caído"
                message: "{{ trigger.to_state.attributes.friendly_name }} no responde."
      default:
        - action: notify.mobile_app_lucass_iphone
          data:
            title: "✅ Servicio recuperado"
            message: "{{ trigger.to_state.attributes.friendly_name }} volvió a responder."
```

Nota: se monitorean con notif solo los no-core (`faceembed`, `mcp`). `salud_ha` está en el dashboard pero no se auto-notifica (si HA cae, no puede notificarse a sí mismo → de eso se encarga el watchdog externo).

- [ ] **Step 2: Commit, deploy, reload, verificar**

```bash
git add homeassistant/automations.yaml
git commit -m "feat: automatización salud_alerta (notif al caer/recuperar servicios)"
git push
ssh r2130 'cd /opt/home-automation && git pull -q && docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -2'
curl -sS -m 10 -X POST -H "$H" $BASE/services/automation/reload >/dev/null && echo "reload ok"
```
Expected: `check_config` sin ERROR; reload ok.

- [ ] **Step 3: Verificar end-to-end (con caída real)**

```bash
ssh r2130 'cd /opt/home-automation && docker compose stop face-embed' ; sleep 75
# debería llegar "⚠️ Servicio caído: Salud face-embed" al iPhone
ssh r2130 'cd /opt/home-automation && docker compose start face-embed' ; sleep 75
# debería llegar "✅ Servicio recuperado: Salud face-embed"
curl -sS -m 5 -H "$H" $BASE/states/automation.salud_alerta_de_servicio | python3 -c 'import json,sys; print("last_triggered:", json.load(sys.stdin)["attributes"].get("last_triggered"))'
```
Expected: llegan ambas notificaciones; `last_triggered` reciente.
Nota: el entity_id de la automatización se genera del alias → `automation.salud_alerta_de_servicio`.

---

### Task 6: Vista "Salud del sistema" en el dashboard

**Files:**
- Modify: `homeassistant/dashboards/remoto.yaml`

- [ ] **Step 1: Agregar la vista al dashboard**

En `homeassistant/dashboards/remoto.yaml`, agregar una vista nueva al final de `views:` (mismo nivel que las vistas "Sala" y "Dormitorio"):

```yaml
  - title: Salud
    path: salud
    icon: mdi:heart-pulse
    cards:
      - type: entities
        title: Estado de servicios
        entities:
          - entity: binary_sensor.salud_ha
            name: Home Assistant
          - entity: binary_sensor.salud_faceembed
            name: FaceEmbed API
          - entity: binary_sensor.salud_mcp
            name: MCP (ha-mcp)
      - type: markdown
        content: >
          **Verde/OK** = servicio respondiendo · **Problema** = no responde.
          `face-recognizer` está pausado a propósito (no se monitorea). El core
          (HA/MQTT/Raspi/internet) lo cubre el watchdog externo de healthchecks.io.
```

- [ ] **Step 2: Commit, deploy**

```bash
git add homeassistant/dashboards/remoto.yaml
git commit -m "feat: vista Salud del sistema en el dashboard"
git push
ssh r2130 'cd /opt/home-automation && git pull -q'
```
Expected: en la app HA, refrescando el dashboard "Control remoto", aparece la pestaña "Salud" con los 3 servicios.

---

### Task 7: Documentación

**Files:**
- Modify: `docs/estado-actual.md`
- Modify: `docs/runbooks/pendientes.md`

- [ ] **Step 1: Actualizar `estado-actual.md`**

En "Integraciones activas en HA" (o en una sección de infra), agregar:
```markdown
| healthmon (`healthmon`) | contenedor, loop ~60s | Health-checks HTTP a face-embed/MCP/HA → `binary_sensor.salud_*` por MQTT. Pinguea healthchecks.io (dead-man switch) si HA OK. Vista "Salud" en el dashboard + `salud_alerta` |
```
En "Entidades y helpers clave":
```markdown
- `binary_sensor.salud_faceembed` / `salud_mcp` / `salud_ha` — salud de servicios (device_class problem)
```

- [ ] **Step 2: Actualizar `pendientes.md`**

En la sección de la refactorización de arquitectura, marcar Observabilidad como HECHO y dejar apuntados los otros dos sub-proyectos:
```markdown
## Refactor de arquitectura (3 sub-proyectos)

- HECHO 2026-09-28: **Observabilidad** — healthmon (health-checks → MQTT), vista "Salud",
  notif `salud_alerta`, watchdog externo healthchecks.io.
- PENDIENTE: **Parametrización** — mover valores casa-específicos (IPs, MACs, IDs Tizen,
  secret_path, grilla) a `secrets.yaml`; compose profiles; doc de onboarding de casa nueva.
- PENDIENTE: **Modularización** — reorganizar la config de HA en packages (tv, house_mode,
  face, presencia...) para que Fase 2 sume packages en vez de engordar automations.yaml.
```

- [ ] **Step 3: Commit**

```bash
git add docs/estado-actual.md docs/runbooks/pendientes.md
git commit -m "docs: observabilidad en estado-actual + sub-proyectos de arquitectura en pendientes"
git push
```

---

## Self-review (cobertura de la spec)

- Contenedor `healthmon` (health-checks HTTP, sin socket, loop resiliente) → **Task 1, 2, 3** ✓
- MQTT Discovery de `binary_sensor.salud_*` → **Task 1 (payload), Task 4 (verificación)** ✓
- Watchdog externo (ping condicional a HA-ok) → **Task 1 (lógica), Task 3 (HEALTHCHECKS_URL)** ✓
- Dashboard "Salud" → **Task 6** ✓
- Notificación al caer/recuperar (transición, anti-spam) → **Task 5** ✓
- Manejo de errores (check aislado, no tumba el loop) → **Task 1** (try/except por servicio) ✓
- Docs → **Task 7** ✓
- Nota de la spec: MQTT/mosquitto sin sensor propio (si cae, sensores `unavailable`) — cubierto por diseño (Task 4 los verá unavailable) y el watchdog externo ✓
