# Home Automation --- Development Handoff

**Versión:** 1.0\
**Fecha:** 2026-09-27\
**Objetivo:** consolidar la plataforma actual, cerrar hardening
pendiente y avanzar hacia presencia física + visión semántica.

------------------------------------------------------------------------

# 1. Objetivo del sprint / siguiente etapa

La infraestructura base ya está suficientemente madura.

**No agregar nuevas capas de infraestructura salvo que sean necesarias
para los objetivos de este documento.**

El próximo trabajo se divide en tres bloques:

``` text
A. Cerrar deuda técnica / hardening
B. Incorporar presencia física confiable
C. Preparar Visual Presence con Frigate + Hailo
```

Prioridad:

``` text
P0  Bugs / seguridad / recovery
P1  Physical Presence
P2  Visual Presence
P3  Semantic Home
P4  Modelos AI avanzados
```

------------------------------------------------------------------------

# 2. Arquitectura actual

``` text
                    INTERFACES
            Siri / HA / ChatGPT / Claude
                       │
                       ▼
                  MCP / Assist
                       │
                       ▼
                HOME ASSISTANT
                       │
             SEMANTIC HOUSE STATE
                       │
       ┌───────────────┼───────────────┐
       │               │               │
    Zigbee          ESPHome         Edge AI
       │               │               │
   sensores         actuadores       Hailo-8
                                       │
                           ┌───────────┼───────────┐
                         YOLO        ArcFace      Pose
```

Principio:

``` text
Hailo          → percepción
Vision Fusion  → interpretación
Home Assistant → estado + reglas + acciones
MCP            → tools semánticas
Agent          → lenguaje + razonamiento
```

------------------------------------------------------------------------

# 3. Principios obligatorios

## Local-first

La casa debe continuar funcionando sin Internet.

## Manual-first

Un fallo de Home Assistant no debe inutilizar interruptores físicos ni
controles esenciales.

## Deterministic-first

Seguridad y acciones críticas no deben depender exclusivamente de
IA/LLM.

## AI as perception

La IA produce señales.

No controla directamente dispositivos críticos.

## Event-driven

Evitar polling cuando existe un evento natural.

## Semantic state

Los agentes deben consumir conceptos de dominio, no cientos de entidades
crudas.

## Observable

Todo servicio crítico debe poder responder:

``` text
¿está vivo?
¿cuánto consume?
¿cuándo falló?
```

------------------------------------------------------------------------

# 4. P0 --- corregir healthmon MCP

## Problema

La implementación actual puede considerar MCP saludable aunque el
endpoint responda un error HTTP.

Patrón problemático:

``` python
requests.get(f"http://{NODE}:9584/", timeout=8)
return True, "ok"
```

`requests.get()` no genera excepción automáticamente ante 4xx/5xx.

## Cambio mínimo

``` python
r = requests.get(f"http://{NODE}:9584/", timeout=8)

if r.status_code >= 500:
    return False, f"HTTP {r.status_code}"

return True, f"HTTP {r.status_code}"
```

## Cambio recomendado

No validar solamente conectividad TCP/HTTP.

Crear o utilizar un health endpoint específico del servicio MCP.

Ejemplo:

``` text
GET /health
```

Respuesta:

``` json
{
  "status": "ok",
  "service": "ha-mcp"
}
```

## Acceptance Criteria

-   MCP detenido → health = DOWN.
-   MCP responde 500 → health = DOWN.
-   MCP operativo → health = UP.
-   timeout → health = DOWN.
-   resultado visible en Home Assistant.
-   alerta sólo después de persistencia razonable para evitar flapping.

------------------------------------------------------------------------

# 5. P0 --- separar Face API de Face Loop

## Problema

Conceptualmente el reconocimiento facial continuo está pausado hasta
integrar Frigate.

Sin embargo, el profile `face` puede volver a levantar el servicio que
captura cámara periódicamente.

No queremos:

``` text
docker compose up
→ face-recognizer
→ /dev/video0 cada 4 s
```

## Refactor

Separar:

``` text
face-api
face-loop
```

### face-api

Responsabilidad:

``` text
image/crop
→ SCRFD
→ ArcFace
→ identity/embedding
```

Debe ser stateless salvo por la DB/config necesaria.

### face-loop

Responsabilidad:

``` text
camera polling
→ face-api
```

Este componente queda:

``` text
DISABLED / EXPERIMENTAL
```

y será eliminado cuando Frigate sea source of events.

## Arquitectura objetivo

``` text
Frigate
   ↓
person event
   ↓
snapshot/crop
   ↓
face-api
   ↓
identity
   ↓
MQTT
```

## Acceptance Criteria

-   `docker compose up -d` normal NO inicia captura periódica.
-   `face-api` puede iniciarse independientemente.
-   el loop experimental requiere profile explícito.
-   README documenta ambos componentes.
-   no hay dos procesos intentando consumir la misma cámara.

------------------------------------------------------------------------

# 6. P0 --- pin de imágenes Docker

## Problema

Evitar dependencias productivas con tags móviles:

``` text
stable
latest
```

Un recreate no debería actualizar software implícitamente.

## Objetivo

Pinnear versiones conocidas.

Ejemplo conceptual:

``` yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:<VERSION>

  cloudflared:
    image: cloudflare/cloudflared:<VERSION>
```

## Proceso de upgrade

``` text
1. revisar release
2. actualizar tag
3. pull
4. deploy
5. health checks
6. rollback si falla
```

## Acceptance Criteria

-   ninguna imagen crítica usa `latest`.
-   documentar versión actual.
-   documentar rollback.
-   `docker compose pull` no cambia versión sin modificación del repo.

------------------------------------------------------------------------

# 7. P0 --- revisar Home Assistant external_url

## Problema a validar

Existe una URL pública asociada al MCP:

``` text
https://ha-mcp.neuralcore.dev
```

Cloudflare termina esa URL en el servicio MCP.

Verificar que:

``` yaml
homeassistant:
  external_url:
```

no esté utilizando la URL del MCP como si fuera la URL canónica de Home
Assistant salvo que exista una razón técnica explícita.

## Riesgos

Home Assistant puede usar `external_url` para:

-   callbacks;
-   links;
-   OAuth;
-   integraciones;
-   URLs generadas.

## Acción

Determinar:

``` text
¿HA necesita external_url?
¿ha_mcp_tools necesita esta URL?
¿la URL corresponde a HA o a MCP?
```

## Acceptance Criteria

-   URL MCP y URL HA tienen semántica clara.
-   no se utiliza una URL MCP como canonical HA URL accidentalmente.
-   decisión documentada en ADR/README.

------------------------------------------------------------------------

# 8. P0 --- hardening MCP

## Estado deseado

Cloudflare Tunnel puede seguir siendo transporte.

No debe ser la única capa de seguridad.

## Objetivo

Migrar progresivamente de:

``` text
secret path = credential
```

a:

``` text
authenticated MCP
+
capability allowlist
```

## Tools permitidas inicialmente

``` text
get_house_state
get_presence
get_room_state
turn_on
turn_off
set_brightness
set_temperature
activate_scene
set_house_mode
```

## No exponer

``` text
unlock
disable_alarm
shell
arbitrary_service_call
admin_home_assistant
arbitrary_yaml
```

## DDL615

Regla explícita:

``` text
MCP/LLM
   ✗
unlock DDL615
```

## Acceptance Criteria

-   autenticación explícita o plan documentado de migración.
-   tools allowlisted.
-   logs de acceso.
-   secrets no hardcodeados.
-   MCP no tiene acceso genérico administrativo a HA.
-   cerraduras fuera del alcance de tools agentic.

------------------------------------------------------------------------

# 9. P0 --- backups

La arquitectura actual ya posee:

``` text
backup local
+
restic
+
R2
+
encryption
+
restore test
```

Mantener.

## Agregar

### Restic check

Programar:

``` bash
restic check
```

semanal.

No ejecutar en cada backup.

### Monitorear edad del último backup

Crear sensor:

``` text
sensor.last_backup_age
```

Alertar si:

``` text
backup age > 36 h
```

o threshold equivalente.

### Revisar SQLite

Validar consistencia de backup de Home Assistant cuando la DB está
activa.

No asumir que copiar:

``` text
home-assistant_v2.db
```

mientras existe WAL garantiza un snapshot consistente.

Evaluar:

``` text
HA backup mechanism
SQLite backup API
checkpoint controlado
```

## Acceptance Criteria

-   backup local diario.
-   backup off-site cifrado.
-   política de retención activa.
-   `restic check` periódico.
-   alerta de backup stale.
-   restore runbook actualizado.
-   restore test reproducible.

------------------------------------------------------------------------

# 10. P1 --- Fase 2: Physical Presence

Esta es la siguiente feature principal.

Objetivo:

``` text
human_present
```

sin depender de cámara.

## Hardware

Incorporar:

``` text
Zigbee coordinator
door sensor
mmWave living
mmWave bedroom opcional
```

## Entidades base

``` text
binary_sensor.entrance_door
binary_sensor.presence_living
binary_sensor.presence_bedroom
```

## Entidades derivadas

``` text
binary_sensor.human_present
binary_sensor.owner_home
```

------------------------------------------------------------------------

# 11. Presence package

Crear:

``` text
packages/presence.yaml
```

Responsabilidad:

``` text
presencia física
+
owner presence
+
door events
→ estado derivado
```

No incluir lógica de cámaras todavía.

## Señales

``` text
owner_home
door_open
living_presence
bedroom_presence
```

Output:

``` text
human_present
```

------------------------------------------------------------------------

# 12. House Mode v2

Mantener:

``` text
HOME
AWAY
CLEANING
NIGHT
```

No agregar modos como:

``` text
CINEMA
PASEO
SIMULATION
```

Estos son contextos.

## Separación

``` text
house_mode
├── HOME
├── AWAY
├── CLEANING
└── NIGHT

context
├── paseo
├── cinema
├── simulation
├── sleeping
└── guest
```

------------------------------------------------------------------------

# 13. Regla AWAY

No usar solamente:

``` text
owner phone away
→ AWAY
```

Usar señales fusionadas.

Ejemplo conceptual:

``` text
owner_home = false
+
human_present = false
+
cleaning_active = false
→ AWAY
```

Aplicar delays/hysteresis.

------------------------------------------------------------------------

# 14. Regla CLEANING

La persona de limpieza debe poder permanecer en casa mientras el owner
está ausente sin que el sistema considere la casa vacía.

Ejemplo:

``` text
owner_home = false
+
cleaning_schedule = true
+
door event
+
human_present = true
→ CLEANING
```

Salida:

``` text
owner_home = false
human_present = true
house_mode = CLEANING
```

------------------------------------------------------------------------

# 15. Perro

Movimiento del perro NO debe producir:

``` text
human_present = true
```

En Fase 2 esto se resuelve principalmente con:

-   ubicación de mmWave;
-   lógica temporal;
-   sensores físicos.

En Fase 3, visión agrega:

``` text
dog_present
```

para mejorar la clasificación.

------------------------------------------------------------------------

# 16. P2 --- Fase 3: Visual Presence

No empezar por CLIP.

Objetivo inicial:

``` text
person
dog
```

## Pipeline

``` text
PoE / RTSP camera
       ↓
     go2rtc
       ↓
     Frigate
       ↓
     Hailo-8
       ↓
   ┌───┴───┐
 person    dog
   │        │
   └───┬────┘
       ↓
      MQTT
```

------------------------------------------------------------------------

# 17. Frigate

Agregar servicio con profile:

``` text
vision
```

Ejemplo conceptual:

``` yaml
profiles:
  - vision
```

No mezclar configuración de visión dentro del core de Home Assistant.

Directorios sugeridos:

``` text
services/
└── frigate/

config/
└── frigate/

models/
└── hailo/
```

------------------------------------------------------------------------

# 18. Frigate zones

Configurar zonas desde el principio.

Ejemplo:

``` text
CAMERA LIVING

┌────────────────────────────┐
│                            │
│       SOFA_ZONE            │
│                            │
│                DOOR_ZONE   │
│                            │
│ BOWL_ZONE                  │
│                            │
└────────────────────────────┘
```

Las zonas serán utilizadas posteriormente por:

-   pose;
-   dog classifier;
-   package detection;
-   context inference.

------------------------------------------------------------------------

# 19. Visual Presence entities

Crear:

``` text
binary_sensor.visual_person_present
binary_sensor.dog_present

sensor.last_person_seen
sensor.last_dog_seen
```

No reemplazar inmediatamente `human_present`.

Primero comparar sensores físicos vs visión.

------------------------------------------------------------------------

# 20. P2 --- Vision Fusion

Crear servicio:

``` text
vision-fusion
```

Inputs iniciales:

``` text
physical/human_present
frigate/person
frigate/dog
door/open
owner_home
```

Outputs:

``` text
human_present
dog_present
```

## Regla

No confiar en una única inferencia.

Aplicar:

``` text
confidence threshold
temporal persistence
hysteresis
sensor fusion
```

------------------------------------------------------------------------

# 21. Estado semántico

Crear un objeto/estado central.

Ejemplo:

``` json
{
  "mode": "AWAY",
  "owner": "away",
  "human_present": false,
  "dog": {
    "present": true,
    "room": "living",
    "activity": null
  },
  "entrance": {
    "door": "closed",
    "package": false,
    "last_person": "18:14"
  },
  "systems": {
    "ha": "ok",
    "vision": "ok",
    "mcp": "ok"
  }
}
```

Inicialmente puede generarse mediante HA templates.

Si crece demasiado, mover a servicio dedicado.

------------------------------------------------------------------------

# 22. P2 --- Face Recognition event-driven

Una vez Frigate operativo:

``` text
Frigate
   ↓
person detected
   ↓
relevant zone
   ↓
best snapshot
   ↓
face-api
   ↓
SCRFD
   ↓
ArcFace
   ↓
identity
   ↓
MQTT
```

Output:

``` text
sensor.visual_identity
binary_sensor.known_person
binary_sensor.unknown_person
```

No utilizar identidad facial para unlock.

------------------------------------------------------------------------

# 23. P3 --- Pose

Sólo después de estabilizar person/dog.

Pipeline:

``` text
person bbox
   ↓
YOLO Pose
   ↓
keypoints
   ↓
temporal rules
```

Estados iniciales:

``` text
standing
sitting
lying
unknown
```

Primera feature:

``` text
sofa_occupied
```

------------------------------------------------------------------------

# 24. Cinema context

Ejemplo:

``` text
sofa_occupied
+
TV ON
+
lux bajo
→ cinema context
```

No convertir CINEMA en `house_mode`.

Output:

``` text
input_boolean.context_cinema
```

o abstracción equivalente.

------------------------------------------------------------------------

# 25. P3 --- Dog classifier

Sólo después de que:

``` text
dog_present
```

sea confiable.

Modelo sugerido:

``` text
MobileNetV3
```

Pipeline:

``` text
Frigate dog bbox
      ↓
crop
      ↓
MobileNetV3
      ↓
ONNX
      ↓
Hailo compiler
      ↓
HEF
      ↓
Hailo-8
```

Clases iniciales:

``` text
sleeping
standing
walking
eating
drinking
unknown
```

`at_door` puede inferirse inicialmente con zona en vez de clase.

------------------------------------------------------------------------

# 26. Dataset dog classifier

Recolectar automáticamente:

``` text
Frigate dog event
       ↓
best crop
       ↓
dataset inbox
```

Estructura:

``` text
dataset/
├── sleeping/
├── standing/
├── walking/
├── eating/
├── drinking/
└── unknown/
```

Crear tooling simple de etiquetado.

No sobreingenierizar.

------------------------------------------------------------------------

# 27. P4 --- CLIP

No implementar antes de completar:

``` text
person/dog
+
vision-fusion
+
pose
```

Uso:

``` text
evento interesante
       ↓
TinyCLIP / MobileCLIP
       ↓
semantic score
```

Casos:

``` text
person cleaning
person carrying package
dog on sofa
```

CLIP nunca debe ser fuente única para una acción crítica.

------------------------------------------------------------------------

# 28. Cascade inference

Arquitectura AI final:

``` text
                 FRAME
                   │
                   ▼
            OBJECT DETECTOR
                   │
          ┌────────┴────────┐
          │                 │
       person              dog
          │                 │
        pose         dog classifier
          │                 │
          └────────┬────────┘
                   │
             evento ambiguo?
                   │
                  YES
                   │
                   ▼
                  CLIP
```

No ejecutar todos los modelos sobre todos los frames.

------------------------------------------------------------------------

# 29. Observabilidad

Mantener el monitor actual.

Agregar progresivamente:

``` text
Frigate FPS
camera FPS
detector latency
Hailo temperature
Hailo availability
vision-fusion health
MQTT availability
backup age
```

Alertas sólo para eventos accionables.

------------------------------------------------------------------------

# 30. Dashboard técnico

Crear una vista:

``` text
SYSTEM HEALTH
─────────────

R2130
CPU
RAM
Temperature
NVMe
SMART

Services
HA
MQTT
MCP
Cloudflare
Frigate
Vision Fusion
Face API

AI
Hailo
Detector latency
Camera status

Backup
Last local backup
Last off-site backup
Restic check
```

------------------------------------------------------------------------

# 31. Dashboard semántico

Separado del técnico.

``` text
HOME
────

Mode             AWAY
Owner            Away
Human present    No

Dog
Present          Yes
Room             Living
Activity         Unknown

Entrance
Door             Closed
Last person      18:14
Package          No

Living
Presence         No
Sofa occupied    No
Cinema           Off
```

------------------------------------------------------------------------

# 32. MCP semántico

Una vez disponible el estado semántico, exponer tools:

``` text
get_house_state()
get_presence()
get_dog_state()
get_security_context()
get_room_state(room)
activate_scene(scene)
set_house_mode(mode)
```

Evitar que el agente necesite conocer:

``` text
binary_sensor.presence_living_2
input_boolean.foo
sensor.xyz
```

------------------------------------------------------------------------

# 33. Ejemplo get_house_state()

``` json
{
  "mode": "AWAY",
  "owner_home": false,
  "human_present": false,
  "dog": {
    "present": true,
    "room": "living",
    "activity": "sleeping"
  },
  "entrance": {
    "door": "closed",
    "package": false
  },
  "health": {
    "home_assistant": "ok",
    "mqtt": "ok",
    "vision": "ok",
    "mcp": "ok"
  }
}
```

------------------------------------------------------------------------

# 34. Seguridad de acciones agentic

Clasificar tools.

## READ

``` text
get_house_state
get_presence
get_dog_state
get_room_state
get_security_context
```

Riesgo bajo.

## WRITE LOW-RISK

``` text
turn_light_on
turn_light_off
set_brightness
set_tv
activate_scene
```

## WRITE MEDIUM-RISK

``` text
set_temperature
set_house_mode
```

Agregar validaciones.

## FORBIDDEN

``` text
unlock
disable_security
execute_shell
arbitrary_service
modify_secrets
```

------------------------------------------------------------------------

# 35. Docker profiles objetivo

Ejemplo:

``` text
core
obs
face-api
vision
experimental
```

Donde:

### core

``` text
HA
MQTT
MCP
Cloudflare
```

### obs

``` text
healthmon
node metrics
```

### face-api

``` text
face inference API
```

### vision

``` text
Frigate
go2rtc
vision-fusion
```

### experimental

``` text
face-loop
CLIP experiments
model tests
```

------------------------------------------------------------------------

# 36. Estructura de repo sugerida

Mantener compatibilidad con la estructura existente.

Objetivo conceptual:

``` text
home-automation/
│
├── compose.yaml
├── .env.example
│
├── packages/
│   ├── tv.yaml
│   ├── house_mode.yaml
│   ├── presence.yaml
│   ├── paseo.yaml
│   ├── seguridad.yaml
│   ├── face.yaml
│   └── health.yaml
│
├── services/
│   ├── healthmon/
│   ├── face-api/
│   ├── vision-fusion/
│   └── frigate/
│
├── config/
│   └── frigate/
│
├── scripts/
│   ├── backup/
│   ├── restore/
│   └── deploy/
│
├── docs/
│   ├── architecture.md
│   ├── recovery.md
│   ├── mcp-security.md
│   └── presence.md
│
└── models/
    └── hailo/
```

No hacer un refactor masivo sólo para alcanzar esta estructura.

Migrar únicamente cuando se toca cada componente.

------------------------------------------------------------------------

# 37. CI mínimo

Agregar checks baratos.

## YAML

Validar sintaxis.

## Docker Compose

``` bash
docker compose config
```

## Python

``` text
ruff
pytest
```

para servicios propios.

## Secrets

Agregar scanner:

``` text
gitleaks
```

o equivalente.

Objetivo:

``` text
PR
 ↓
syntax
 ↓
secrets scan
 ↓
tests
 ↓
merge
```

------------------------------------------------------------------------

# 38. No hacer todavía

No implementar ahora:

``` text
Kubernetes
Prometheus/Grafana completo
vector database
VLM local pesado
LLM en Hailo
FastSAM productivo
depth estimation productivo
múltiples cámaras interiores
auto-unlock
facial auth
custom event bus adicional a MQTT
```

Evitar aumentar complejidad antes de que exista necesidad real.

------------------------------------------------------------------------

# 39. Orden de implementación

## Sprint A --- Hardening

``` text
[ ] fix healthmon MCP
[ ] separar face-api / face-loop
[ ] pin Docker images
[ ] revisar external_url
[ ] hardening MCP
[ ] restic check
[ ] backup age alert
[ ] validar SQLite backup
[ ] CI secrets scan
```

## Sprint B --- Physical Presence

``` text
[ ] Zigbee coordinator
[ ] door sensor
[ ] mmWave living
[ ] packages/presence.yaml
[ ] human_present
[ ] owner_home
[ ] house_mode v2
[ ] CLEANING logic
[ ] tests de transiciones
```

## Sprint C --- Visual Presence

``` text
[ ] Frigate
[ ] go2rtc
[ ] Hailo detector
[ ] person
[ ] dog
[ ] zones
[ ] MQTT
[ ] HA visual sensors
```

## Sprint D --- Fusion

``` text
[ ] vision-fusion
[ ] physical + visual presence
[ ] dog_present
[ ] human_present v2
[ ] semantic state
[ ] dashboard semántico
```

## Sprint E --- Edge AI

``` text
[ ] FaceEmbed event-driven
[ ] pose
[ ] sofa_occupied
[ ] dog dataset
[ ] MobileNetV3
[ ] ONNX → HEF
[ ] dog_activity
```

## Sprint F --- Agentic Home

``` text
[ ] semantic MCP tools
[ ] get_house_state
[ ] get_presence
[ ] get_dog_state
[ ] tool permissions
[ ] audit/logging
```

------------------------------------------------------------------------

# 40. Definition of Done --- Physical Presence

La fase se considera completa cuando estos escenarios funcionan de forma
estable:

### Owner en casa

``` text
owner_home = true
human_present = true
house_mode = HOME
```

### Owner sale, perro queda

``` text
owner_home = false
human_present = false
dog_present = true/unknown
house_mode = AWAY
```

El movimiento del perro no debe producir HOME.

### Limpieza

``` text
owner_home = false
human_present = true
cleaning_active = true
house_mode = CLEANING
```

### Noche

``` text
owner_home = true
house_mode = NIGHT
```

Las transiciones deben tolerar breves pérdidas de sensores.

------------------------------------------------------------------------

# 41. Definition of Done --- Visual Presence

``` text
person detectado de forma estable
dog detectado de forma estable
zonas funcionando
MQTT estable
HA recibe eventos
camera offline detectable
Hailo offline detectable
```

Y:

``` text
person != dog
```

debe mantenerse con una tasa de falsos positivos suficientemente baja
para automatizaciones domésticas.

------------------------------------------------------------------------

# 42. Definition of Done --- Semantic Home

Debe poder obtenerse una única representación:

``` json
{
  "mode": "HOME|AWAY|CLEANING|NIGHT",
  "owner_home": true,
  "human_present": true,
  "dog": {
    "present": true,
    "room": "living",
    "activity": "sleeping"
  },
  "entrance": {
    "door": "closed"
  },
  "health": {
    "ha": "ok",
    "mqtt": "ok",
    "vision": "ok",
    "mcp": "ok"
  }
}
```

No importa inicialmente si internamente se genera mediante templates HA
o un servicio.

La interfaz semántica debe permanecer estable.

------------------------------------------------------------------------

# 43. Resultado esperado

El sistema debe evolucionar de:

``` text
"prendé la TV"
```

a:

``` text
"¿qué pasa en casa?"
```

con una respuesta basada en estado real:

``` text
Owner fuera.
No hay personas detectadas.
El perro está en el living.
La puerta está cerrada.
Los sistemas principales están operativos.
```

La arquitectura final debe mantener:

``` text
MUNDO FÍSICO
     ↓
PERCEPCIÓN
     ↓
FUSIÓN
     ↓
ESTADO SEMÁNTICO
     ↓
HOME ASSISTANT
     ↓
AUTOMATIZACIONES
```

y:

``` text
ESTADO SEMÁNTICO
      ↓
     MCP
      ↓
    AGENTE
```

------------------------------------------------------------------------

# 44. Prioridad inmediata para desarrollo

Empezar por:

``` text
1. healthmon MCP
2. face-api / face-loop
3. Docker pinning
4. external_url
5. MCP hardening
6. restic check + backup alert
```

Una vez mergeado:

``` text
Fase 2 — Physical Presence
```

No comenzar CLIP, pose ni dog classifier antes de completar
`human_present` de forma confiable.

El criterio rector de la siguiente etapa es:

> **Primero hacer confiable el estado de la casa. Después hacerlo
> inteligente.**
