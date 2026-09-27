# Integración face rec → HA — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que HA sepa quién ve la cámara vía un contenedor `face-recognizer` que reconoce en loop y publica a MQTT, con sensor, notificaciones y señal blanda de presencia. Según `docs/superpowers/specs/2026-09-27-face-rec-ha-design.md`.

**Architecture:** Contenedor Python nuevo (`face-recognizer`) captura de `/dev/video0`, consulta al `face-embed` existente, y publica estado/atributos a Mosquitto con MQTT Discovery. HA crea `sensor.ultima_cara` solo y dos automatizaciones reaccionan. Todo local.

**Tech Stack:** Python 3.11, ffmpeg (captura v4l2), paho-mqtt 1.6.1, requests. MQTT (Mosquitto ya corriendo). HA MQTT Discovery.

**Notas de entorno:** `face-recognizer` corre en la red default de compose → llega a `face-embed:8000` y `mosquitto:1883` por nombre. HA (network_mode host) lee del mismo broker Mosquitto. Credenciales MQTT del `.env` (`MQTT_USER`/`MQTT_PASSWORD`). Comandos desde el mini-PC; deploy con `git pull` en la R2130.

```bash
# helpers de terminal
TOKEN=$(cat ~/.ha_token); H="Authorization: Bearer $TOKEN"; BASE=http://192.168.1.17:8123/api
```

---

### Task 1: Script del loop (`face-recognizer/loop.py`)

**Files:**
- Create: `face-recognizer/loop.py`

- [ ] **Step 1: Escribir `face-recognizer/loop.py`**

```python
#!/usr/bin/env python3
"""Loop de reconocimiento facial → MQTT para Home Assistant.
Captura /dev/video0 cada INTERVAL s, consulta al face-embed, y publica a MQTT
el último reconocido (lucas / desconocido / nadie) con MQTT Discovery.
"""
import base64, json, os, subprocess, time, datetime
import requests
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "ha")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
FACE_EMBED_URL = os.environ.get("FACE_EMBED_URL", "http://face-embed:8000")
COLLECTION = os.environ.get("COLLECTION", "depto")
THRESHOLD = float(os.environ.get("THRESHOLD", "0.45"))
INTERVAL = float(os.environ.get("INTERVAL", "4"))
VIDEO_DEV = os.environ.get("VIDEO_DEV", "/dev/video0")

STATE_TOPIC = "depto/face/state"
ATTRS_TOPIC = "depto/face/attrs"
DISCOVERY_TOPIC = "homeassistant/sensor/face_ultima_cara/config"
DISCOVERY_PAYLOAD = {
    "name": "Última cara",
    "unique_id": "face_ultima_cara",
    "state_topic": STATE_TOPIC,
    "json_attributes_topic": ATTRS_TOPIC,
    "icon": "mdi:face-recognition",
}


def capture_jpg(path="/tmp/f.jpg"):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "v4l2", "-i", VIDEO_DEV,
         "-frames:v", "1", "-q:v", "3", path],
        check=True, timeout=15,
    )
    return path


def recognize():
    """Devuelve (estado, similarity). estado: user_id | 'desconocido' | 'nadie'."""
    path = capture_jpg()
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    faces = requests.post(f"{FACE_EMBED_URL}/detect_and_embed",
                          json={"image_base64": img, "confidence_threshold": 0.5},
                          timeout=20).json()
    if not faces:
        return "nadie", None
    faces.sort(key=lambda x: x.get("detection_confidence", 0), reverse=True)
    vec = faces[0]["embedding"]["vector"]
    res = requests.post(f"{FACE_EMBED_URL}/vectors/search",
                        json={"collection": COLLECTION, "vector": vec, "threshold": THRESHOLD},
                        timeout=20).json()
    results = res.get("results") or []
    if res.get("status") == "found" and results:
        return results[0]["user_id"], round(float(results[0]["similarity"]), 3)
    return "desconocido", None


def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    client.publish(DISCOVERY_TOPIC, json.dumps(DISCOVERY_PAYLOAD), qos=1, retain=True)
    print("face-recognizer iniciado", flush=True)
    while True:
        try:
            estado, sim = recognize()
            attrs = {"similarity": sim, "visto": datetime.datetime.now().isoformat(timespec="seconds")}
            client.publish(STATE_TOPIC, estado, qos=0, retain=True)
            client.publish(ATTRS_TOPIC, json.dumps(attrs), qos=0, retain=True)
            print("estado:", estado, "sim:", sim, flush=True)
        except Exception as e:
            print("error en ciclo:", repr(e), flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add face-recognizer/loop.py
git commit -m "feat: loop.py del face-recognizer (reconocimiento → MQTT)"
```

---

### Task 2: Dockerfile del `face-recognizer`

**Files:**
- Create: `face-recognizer/Dockerfile`

- [ ] **Step 1: Escribir `face-recognizer/Dockerfile`**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests==2.31.0 paho-mqtt==1.6.1

COPY loop.py /app/loop.py
WORKDIR /app
CMD ["python3", "-u", "loop.py"]
```

- [ ] **Step 2: Commit**

```bash
git add face-recognizer/Dockerfile
git commit -m "feat: Dockerfile del face-recognizer"
```

---

### Task 3: Servicio en docker-compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Agregar el servicio `face-recognizer`**

En `docker-compose.yml`, después del bloque `face-embed` (antes de `cloudflared-mcp`), agregar:

```yaml
  # Loop de reconocimiento facial → MQTT (consume face-embed, publica a Home Assistant).
  face-recognizer:
    build: ./face-recognizer
    container_name: face-recognizer
    restart: unless-stopped
    devices:
      - /dev/video0:/dev/video0
    environment:
      - TZ=${TZ}
      - MQTT_HOST=mosquitto
      - MQTT_USER=${MQTT_USER}
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - FACE_EMBED_URL=http://face-embed:8000
    depends_on:
      - mosquitto
      - face-embed
```

- [ ] **Step 2: Commit, push, deploy y build**

```bash
git add docker-compose.yml
git commit -m "feat: servicio face-recognizer en compose"
git push
ssh r2130 'cd /opt/home-automation && git pull -q && docker compose build face-recognizer 2>&1 | tail -5 && docker compose up -d face-recognizer'
```
Expected: build OK, contenedor `face-recognizer` levantado.

- [ ] **Step 3: Verificar que publica a MQTT**

```bash
ssh r2130 'docker logs face-recognizer --since 30s 2>&1 | tail -6'
```
Expected: líneas `face-recognizer iniciado` y `estado: nadie/lucas/... sim: ...` cada ~4 s.

Verificar los topics en el broker:
```bash
ssh r2130 'cd /opt/home-automation && source .env && docker exec mosquitto mosquitto_sub -u $MQTT_USER -P $MQTT_PASSWORD -t "depto/face/#" -C 2 -W 10'
```
Expected: aparece un valor de estado (`nadie` o `lucas`) y el JSON de atributos.

---

### Task 4: Verificar el sensor en HA (MQTT Discovery)

**Files:** ninguno (HA crea el sensor solo desde el discovery retained).

- [ ] **Step 1: Confirmar que `sensor.ultima_cara` existe**

```bash
curl -sS -m 5 -H "$H" $BASE/states/sensor.ultima_cara | python3 -c 'import json,sys; d=json.load(sys.stdin); print("estado:", d.get("state"), "| attrs:", d.get("attributes"))'
```
Expected: `estado: nadie` (o `lucas` si estás frente a la cámara), con atributos `similarity` y `visto`. Si da 404, esperar ~15 s (discovery) o reiniciar la integración MQTT.

- [ ] **Step 2: Prueba en vivo**

Ponerse frente a la cámara ~5 s y volver a consultar:
```bash
curl -sS -m 5 -H "$H" $BASE/states/sensor.ultima_cara | python3 -c 'import json,sys; d=json.load(sys.stdin); print("estado:", d.get("state"), "| sim:", d.get("attributes",{}).get("similarity"))'
```
Expected: `estado: lucas` con `sim` ~0.6-0.85.

---

### Task 5: Helper `input_boolean.lucas_visto_camara`

**Files:**
- Modify: `homeassistant/configuration.yaml`

- [ ] **Step 1: Agregar el helper**

En `homeassistant/configuration.yaml`, dentro del bloque `input_boolean:` existente (donde están `modo_paseo` y `modo_simulacion`), agregar:

```yaml
  lucas_visto_camara:
    name: Lucas visto por cámara
    icon: mdi:face-recognition
```

- [ ] **Step 2: Commit, deploy y restart**

```bash
git add homeassistant/configuration.yaml
git commit -m "feat: helper lucas_visto_camara"
git push
ssh r2130 'cd /opt/home-automation && git pull -q && docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -2 && docker restart homeassistant'
```
Expected: `check_config` sin ERROR.

- [ ] **Step 3: Verificar**

```bash
sleep 40; curl -sS -m 5 -H "$H" $BASE/states/input_boolean.lucas_visto_camara | python3 -c 'import json,sys; print("estado:", json.load(sys.stdin)["state"])'
```
Expected: `estado: off`.

---

### Task 6: Automatizaciones (notificación + señal blanda)

**Files:**
- Modify: `homeassistant/automations.yaml`

- [ ] **Step 1: Agregar las dos automatizaciones**

Al final de `homeassistant/automations.yaml`, agregar:

```yaml
- id: face_reconocido
  alias: "Face: notificar reconocimiento"
  description: "Notifica al iPhone cuando cambia quién ve la cámara (transición real, no 'nadie')."
  triggers:
    - trigger: state
      entity_id: sensor.ultima_cara
  conditions:
    - condition: template
      value_template: >
        {{ trigger.from_state.state != trigger.to_state.state
           and trigger.to_state.state not in ['nadie', 'unknown', 'unavailable', ''] }}
  actions:
    - choose:
        - conditions:
            - condition: template
              value_template: "{{ trigger.to_state.state == 'desconocido' }}"
          sequence:
            - action: notify.mobile_app_lucass_iphone
              data:
                title: "⚠️ Cara desconocida"
                message: "La cámara detectó una cara no reconocida."
      default:
        - action: notify.mobile_app_lucass_iphone
          data:
            title: "👋 Reconocido"
            message: "La cámara reconoció a {{ trigger.to_state.state }}."

- id: face_lucas_presencia
  alias: "Face: señal blanda de presencia de Lucas"
  description: "Prende lucas_visto_camara al reconocer a Lucas; lo apaga tras 3 min sin verlo."
  triggers:
    - trigger: state
      entity_id: sensor.ultima_cara
      to: "lucas"
      id: visto
    - trigger: state
      entity_id: sensor.ultima_cara
      for: "00:03:00"
      id: ausente
  actions:
    - choose:
        - conditions:
            - condition: trigger
              id: visto
          sequence:
            - action: input_boolean.turn_on
              target:
                entity_id: input_boolean.lucas_visto_camara
        - conditions:
            - condition: trigger
              id: ausente
            - condition: template
              value_template: "{{ not is_state('sensor.ultima_cara', 'lucas') }}"
          sequence:
            - action: input_boolean.turn_off
              target:
                entity_id: input_boolean.lucas_visto_camara
```

- [ ] **Step 2: Commit, deploy, reload**

```bash
git add homeassistant/automations.yaml
git commit -m "feat: automatizaciones face (notif + presencia blanda)"
git push
ssh r2130 'cd /opt/home-automation && git pull -q && docker exec homeassistant python -m homeassistant --script check_config -c /config 2>&1 | tail -2'
curl -sS -m 10 -X POST -H "$H" $BASE/services/automation/reload >/dev/null && echo "reload ok"
```
Expected: `check_config` sin ERROR; reload ok.

- [ ] **Step 3: Verificar end-to-end**

- Ponerse frente a la cámara → en ~4-8 s debería llegar la notif "👋 Reconocido: lucas" al iPhone, y `input_boolean.lucas_visto_camara` pasar a `on`:
```bash
curl -sS -m 5 -H "$H" $BASE/states/input_boolean.lucas_visto_camara | python3 -c 'import json,sys; print("lucas_visto:", json.load(sys.stdin)["state"])'
```
Expected: `on` mientras estás; `off` tras 3 min sin verte.

- Verificar que las automatizaciones existen (entity_id se genera del alias):
```bash
curl -sS -m 5 -H "$H" $BASE/states | python3 -c '
import json,sys
for e in json.load(sys.stdin):
    if e["entity_id"].startswith("automation.face"): print(e["entity_id"], "=", e["state"])'
```
Expected: `automation.face_notificar_reconocimiento` y `automation.face_senal_blanda_de_presencia_de_lucas`, ambas `on`.

---

### Task 7: Documentación

**Files:**
- Modify: `docs/estado-actual.md`

- [ ] **Step 1: Actualizar `estado-actual.md`**

En la tabla de "Integraciones activas en HA", agregar bajo la fila de FaceEmbed:

```markdown
| face-recognizer (`face-recognizer`) | contenedor, loop ~4s | Captura `/dev/video0` → face-embed → MQTT. Crea `sensor.ultima_cara` (lucas/desconocido/nadie) por Discovery. Alimenta notif + `input_boolean.lucas_visto_camara` (señal blanda) |
```

En "Entidades y helpers clave", agregar:
```markdown
- `sensor.ultima_cara` — último reconocido por la cámara (vía MQTT); atributos `similarity`, `visto`
- `input_boolean.lucas_visto_camara` — señal blanda: Lucas visto por cámara (no cambia house_mode solo)
```

En la tabla de "Automatizaciones", agregar:
```markdown
| `face_reconocido` / `face_lucas_presencia` | Notif al reconocer (o desconocido); prende/apaga lucas_visto_camara |
```

- [ ] **Step 2: Commit**

```bash
git add docs/estado-actual.md
git commit -m "docs: face-recognizer integrado a HA en estado-actual"
git push
```

---

## Self-review (cobertura de la spec)

- Contenedor `face-recognizer` (loop captura→face-embed→MQTT, manejo de errores) → **Task 1, 2, 3** ✓
- MQTT Discovery + `sensor.ultima_cara` → **Task 1 (payload), Task 4 (verificación)** ✓
- Helper `input_boolean.lucas_visto_camara` (+ Siri/HomeKit) → **Task 5** (nota: exponer a HomeKit es opcional; el helper básico va en Task 5; agregar al filtro HomeKit si se quiere Siri) ✓
- Notificación (conocido/desconocido, anti-spam por transición) → **Task 6** ✓
- Señal blanda de presencia (on al ver, off a los 3 min) → **Task 6** ✓
- Manejo de errores (loop resiliente, reconexión) → **Task 1** (try/except + `restart: unless-stopped`) ✓
- Docs → **Task 7** ✓
