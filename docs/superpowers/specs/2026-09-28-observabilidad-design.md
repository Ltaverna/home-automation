# Spec: Observabilidad / salud del sistema

**Fecha:** 2026-09-28
**Estado:** aprobado
**Contexto:** Primer sub-proyecto del refactor de arquitectura (ver
[`estado-actual.md`](../../estado-actual.md)). Los otros dos —parametrización/`secrets.yaml`
y modularización/packages— van en ciclos propios después.

## Objetivo

Enterarse si algo del sistema deja de funcionar: dashboard de salud en HA + notificación al
iPhone para servicios no-core, y un watchdog externo para el caso "core caído" (HA/MQTT/Raspi/
internet), que la notificación interna no puede cubrir.

## Decisiones (del brainstorming)

- **Ambas**: dashboard de salud + notificación proactiva.
- **Watchdog externo** vía dead-man switch (healthchecks.io).
- **Health-checks HTTP**, sin montar el socket de Docker (mide "¿el servicio responde?", que es
  lo que importa, y evita dar acceso root al host a un contenedor).

## Arquitectura

```
healthmon (contenedor, loop ~60s)
  ├─ GET face-embed:8000/health        ─┐
  ├─ GET localhost:9584 (ha-mcp)        ├─► publica binary_sensor por MQTT Discovery ─► HA
  ├─ GET 192.168.1.17:8123 (HA)         │        (salud_faceembed, salud_mcp, ...)
  ├─ conexión MQTT (implícita)         ─┘
  └─ si HA OK → ping healthchecks.io ──────► dead-man switch (avisa si deja de pingar)

HA: dashboard "Salud" (tab) + automatización de notificación (no-core)
```

## Componente `healthmon`

- Imagen: `python:3.11-slim` + pip `requests`, `paho-mqtt==1.6.1` (mismo patrón que `face-recognizer`).
- Red de compose (llega a `face-embed:8000` y `mosquitto:1883` por nombre); HA y ha-mcp se
  chequean por IP/host del nodo (`192.168.1.17:8123`, `localhost:9584` no es alcanzable desde la
  red bridge → se usa `192.168.1.17:9584`).
- Config por entorno: `MQTT_USER`, `MQTT_PASSWORD` (de `.env`), `HEALTHCHECKS_URL` (de `.env`),
  `INTERVAL` (60), y las URLs de los checks.
- Loop (`monitor.py`):
  1. Para cada servicio, hace el health-check (timeout corto) → `ok` / `fail`.
     - `face-embed`: `GET http://face-embed:8000/health` → 200 y JSON con `status: ok`.
     - `ha-mcp`: `GET http://192.168.1.17:9584/` → cualquier respuesta HTTP (incluye 404) = vivo;
       sin conexión = caído.
     - `ha`: `GET http://192.168.1.17:8123/` → 200/302 = vivo.
  2. Publica cada resultado a `depto/salud/<servicio>` (`ON`=problema / `OFF`=ok, semántica
     `device_class: problem`) + `depto/salud/<servicio>/attrs` con `{checked, detail}`.
  3. Si el check de `ha` fue OK → `GET HEALTHCHECKS_URL` (ping dead-man). Si HA falla o el ciclo
     entero falla, no se pinguea → healthchecks.io alerta externamente.
  4. Publica el MQTT Discovery (retained) de cada `binary_sensor` al arrancar.
  5. Captura excepciones por servicio (un check que falla no tumba el loop).
- `restart: unless-stopped`.

### MQTT Discovery (por cada servicio)

Ejemplo para face-embed, retained a `homeassistant/binary_sensor/salud_faceembed/config`:
```json
{
  "name": "Salud face-embed",
  "unique_id": "salud_faceembed",
  "state_topic": "depto/salud/faceembed",
  "json_attributes_topic": "depto/salud/faceembed/attrs",
  "device_class": "problem",
  "payload_on": "ON",
  "payload_off": "OFF"
}
```
Servicios monitoreados: `faceembed`, `mcp`, `ha`. (`face-recognizer` está pausado → no se
monitorea; se documenta como "pausado esperado". MQTT/mosquitto es implícito: si cae, el monitor
no publica nada y sus sensores quedan `unavailable`, lo que el dashboard muestra.)

## Watchdog externo (healthchecks.io)

- El usuario crea un check gratuito en healthchecks.io → obtiene la URL de ping (`https://hc-ping.com/<uuid>`).
- Se guarda en `.env` como `HEALTHCHECKS_URL` (secreto, fuera de git).
- El monitor la pinguea **solo si HA respondió OK** en ese ciclo → el ping depende de la salud
  del core. Período esperado: 60s; configurar en healthchecks.io grace de ~5 min.
- Si HA/MQTT/la Raspi/internet caen → sin ping → healthchecks.io notifica por email/push
  (configurable en su panel).

## Home Assistant

### Dashboard "Salud del sistema"
Nueva vista en el dashboard `remoto-tv` (o dashboard propio) con:
- Una tarjeta de entidades con `binary_sensor.salud_faceembed`, `salud_mcp`, `salud_ha`.
- Estado visual (problema/ok) + atributo `checked` (última verificación).

### Automatización `salud_alerta` (`automations.yaml`)
- Trigger: cualquiera de los `binary_sensor.salud_*` (no-core) cambia a `on` (problema) o a `off`
  (recuperado).
- Acción: notificar al iPhone — "⚠️ <servicio> no responde" al caer, "✅ <servicio> recuperado"
  al volver. La transición de estado evita spam (solo notifica en cambios, no cada 60s).

## Archivos

- `healthmon/Dockerfile`, `healthmon/monitor.py`
- `docker-compose.yml` — servicio `healthmon`
- `.env.example` — documentar `HEALTHCHECKS_URL` (el valor real va en `.env`, fuera de git)
- `homeassistant/dashboards/remoto.yaml` — vista "Salud" (o dashboard nuevo)
- `homeassistant/automations.yaml` — `salud_alerta`

## Manejo de errores

- Cada health-check está aislado en try/except; un servicio caído no rompe el loop ni impide
  chequear los demás.
- Reconexión MQTT automática (paho `reconnect`).
- Si el propio `healthmon` muere, `restart: unless-stopped` lo relevanta; y si no, el ping a
  healthchecks.io se detiene → el watchdog externo lo detecta (el monitor es parte del "core"
  vigilado indirectamente).

## Criterios de éxito

- En HA aparecen solos `binary_sensor.salud_faceembed`, `salud_mcp`, `salud_ha` reflejando el
  estado real (probar parando `face-embed` → su sensor pasa a "problema" en ≤60s).
- Llega notif al iPhone al caer un servicio no-core y otra al recuperarse (sin spam).
- La vista "Salud" muestra el estado de cada servicio.
- healthchecks.io recibe pings cada ~60s; al parar HA (o el monitor), deja de recibirlos y alerta.

## Fuera de alcance

- Monitoreo de recursos (CPU/RAM/disco/temperatura de la Raspi) — se puede sumar después.
- Auto-reparación (reiniciar contenedores caídos) — por ahora solo alertar, no actuar.
- Monitoreo de los túneles/servicios ajenos al proyecto (crypto-bot, consorcio).
