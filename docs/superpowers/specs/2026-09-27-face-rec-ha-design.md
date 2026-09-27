# Spec: Integración de reconocimiento facial → Home Assistant

**Fecha:** 2026-09-27
**Estado:** aprobado
**Contexto:** Sobre el PoC de face rec ya funcionando (`face-embed`, HailoRT 4.20, ver
[`estado-actual.md`](../../estado-actual.md) y [`referencia-arcface.md`](../../referencia-arcface.md)).
Cámara USB de laboratorio (`/dev/video0`); no está en la entrada todavía.

## Objetivo

Que Home Assistant sepa "quién ve la cámara" y reaccione: un sensor con el último reconocido,
notificaciones al iPhone, y una señal blanda de presencia. Todo local, vía MQTT.

## Decisiones (del brainstorming)

- **Trigger:** loop continuo (~4 s). Simple para PoC; en producción se limitaría por presencia.
- **Acciones en HA:** (1) sensor con el último reconocido, (2) notificación al iPhone,
  (3) influir en house_mode como señal blanda.
- **Face rec = señal blanda**, nunca credencial (ArcFace no tiene liveness — ver referencia).

## Arquitectura

```
face-recognizer (contenedor)                        Home Assistant
  loop cada ~4s:                                     ┌──────────────────────────┐
    ffmpeg captura /dev/video0                       │ sensor.ultima_cara        │
    → POST face-embed:8000/detect_and_embed          │  (Lucas/desconocido/nadie)│
    → POST /vectors/search (threshold 0.45)          │ + attrs: similarity, visto│
    → decide estado                                  │ input_boolean.lucas_visto │
    → publica a MQTT ──────────► mosquitto ──────────► automatizaciones          │
                                                     └──────────────────────────┘
```

Dos contenedores separados (responsabilidad única):
- **`face-embed`** (ya existe): el motor. API HTTP, corre los modelos en el Hailo.
- **`face-recognizer`** (nuevo): el loop. Captura, consulta al motor, publica a MQTT. No toca el Hailo directo.

## Componente `face-recognizer`

- Imagen: `python:3.11-slim` + `ffmpeg` (captura) + pip `requests`, `paho-mqtt`.
- Acceso: `devices: /dev/video0`; red de compose para llegar a `face-embed:8000` y `mosquitto:1883`.
- Config por entorno: `MQTT_USER`, `MQTT_PASSWORD` (de `.env`), intervalo, threshold, colección.
- Loop (`loop.py`):
  1. `ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 /tmp/f.jpg` (un frame).
  2. base64 → POST `http://face-embed:8000/detect_and_embed` (confidence 0.5).
  3. Si 0 caras → estado `nadie`. Si hay cara → POST `/vectors/search` (threshold 0.45):
     - match → estado = `user_id` (ej. `lucas`), guarda `similarity`.
     - sin match → estado `desconocido`.
  4. Publica estado a `depto/face/state` y atributos JSON (`similarity`, `visto` ISO time) a
     `depto/face/attrs`.
  5. Espera el intervalo (~4 s). Reintenta ante errores sin morir.
- Al arrancar: publica el **MQTT Discovery** (retained) para el sensor.

## MQTT Discovery

Publicar (retained) a `homeassistant/sensor/face_ultima_cara/config`:

```json
{
  "name": "Última cara",
  "unique_id": "face_ultima_cara",
  "state_topic": "depto/face/state",
  "json_attributes_topic": "depto/face/attrs",
  "icon": "mdi:face-recognition"
}
```

HA crea solo `sensor.ultima_cara`. Estado: `lucas` / `desconocido` / `nadie`. Atributos:
`similarity` (float), `visto` (timestamp ISO).

## Home Assistant

### Helper (`configuration.yaml`)
```yaml
input_boolean:
  lucas_visto_camara:
    name: Lucas visto por cámara
    icon: mdi:face-recognition
```
(se expone a Siri/HomeKit igual que los otros).

### Automatizaciones (`automations.yaml`)

- **`face_reconocido`**: trigger = `sensor.ultima_cara` cambia. Solo actúa en transición real
  (from != to) y si el nuevo estado NO es `nadie`.
  - Si el estado es un conocido (`lucas`): notificar "👋 Reconocí a Lucas en la cámara".
  - Si es `desconocido`: notificar "⚠️ Cara desconocida en la cámara".
  - Cooldown: la condición `from != to` ya evita repetir el mismo estado; además no se
    re-notifica mientras el estado se mantiene (el loop publica el mismo valor → no hay cambio
    de estado en HA, no dispara).

- **`face_lucas_presencia`**:
  - trigger = `sensor.ultima_cara` pasa a `lucas` → `input_boolean.turn_on lucas_visto_camara`.
  - trigger = `sensor.ultima_cara` deja de ser `lucas` por `for: 00:03:00` →
    `input_boolean.turn_off lucas_visto_camara`.
  - Es señal **blanda**: no cambia `house_mode` por sí sola (el geofence sigue mandando). Queda
    disponible para futuras reglas (ej. combinar con puerta en Fase 2).

## Archivos

- `face-recognizer/Dockerfile`, `face-recognizer/loop.py`
- `docker-compose.yml` — servicio `face-recognizer`
- `homeassistant/configuration.yaml` — `input_boolean.lucas_visto_camara`
- `homeassistant/automations.yaml` — `face_reconocido`, `face_lucas_presencia`

## Manejo de errores

- El loop captura excepciones (cámara ocupada, face-embed caído, MQTT desconectado) y reintenta
  al siguiente ciclo sin morir (`restart: unless-stopped` como red de seguridad).
- Si `face-embed` no responde, publica estado `nadie` (o mantiene el último) y sigue.
- Reconexión MQTT automática (paho-mqtt `reconnect`).

## Criterios de éxito

- `sensor.ultima_cara` aparece solo en HA (MQTT Discovery) y refleja en vivo: `lucas` cuando
  estás frente a la cámara, `nadie` cuando no, `desconocido` con otra cara.
- Llega notificación al iPhone al reconocerte (y al aparecer un desconocido), sin spam.
- `input_boolean.lucas_visto_camara` se prende al reconocerte y se apaga a los 3 min sin verte.

## Fuera de alcance

- Cambiar `house_mode` automáticamente por face rec (queda como señal blanda; se evaluará en
  Fase 2 combinando con sensores).
- Cámara en la entrada / producción (Fase 4 con la PoE + Frigate).
- Liveness / anti-spoofing (no disponible; por eso nunca es credencial).
