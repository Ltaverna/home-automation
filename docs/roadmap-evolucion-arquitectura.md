# Home Automation Platform --- Evolución, Arquitectura Objetivo y Roadmap

**Versión:** 1.0\
**Fecha:** 2026-09-27\
**Estado:** plataforma operativa en evolución

------------------------------------------------------------------------

# 1. Resumen ejecutivo

El proyecto dejó de ser una instalación doméstica de Home Assistant para
convertirse en una **plataforma local de automatización, Edge AI y
control agentic**.

La evolución más importante no es la cantidad de dispositivos
integrados, sino la separación de responsabilidades que empezó a
aparecer:

``` text
Percepción
    ↓
Contexto
    ↓
Estado de la casa
    ↓
Automatizaciones
    ↓
Dispositivos
```

por encima de la cual se agrega:

``` text
MCP
 ↓
Agentes
```

Home Assistant continúa siendo la autoridad sobre el estado y la
ejecución.

El MCP no reemplaza Home Assistant: proporciona una interfaz semántica
para agentes.

El Hailo-8 tampoco reemplaza Home Assistant ni al agente: proporciona
percepción visual local.

La arquitectura objetivo queda, conceptualmente:

``` text
Hailo-8       → percepción
Vision Fusion → interpretación
Home Assistant→ estado + reglas + acciones
MCP           → herramientas semánticas
LLM/Agent     → lenguaje + razonamiento
```

------------------------------------------------------------------------

# 2. Estado actual

El proyecto ya cuenta con una base operativa significativa.

Entre las piezas implementadas o encaminadas se encuentran:

-   nodo central basado en reComputer AI R2130;
-   Raspberry Pi 5 + Hailo-8;
-   almacenamiento NVMe;
-   Home Assistant containerizado;
-   Mosquitto/MQTT;
-   control real de televisores;
-   integración HomeKit/Siri;
-   modos globales de casa;
-   modo paseo;
-   simulación de presencia/seguridad;
-   backups;
-   health monitoring;
-   servicios desacoplados;
-   reconocimiento facial experimental;
-   Hailo como acelerador real;
-   MQTT Discovery;
-   MCP para control/consulta;
-   Cloudflare Tunnel;
-   documentación de onboarding;
-   configuración modular por packages;
-   Docker Compose Profiles.

Esto marca una diferencia importante:

``` text
ANTES
Home Assistant + automatizaciones

AHORA
plataforma doméstica local
+ Edge AI
+ estado semántico
+ agentes
```

------------------------------------------------------------------------

# 3. Evolución arquitectónica

La primera versión podía representarse como:

``` text
sensores
   ↓
Home Assistant
   ↓
dispositivos
```

La arquitectura actual empieza a ser:

``` text
                         INTERFACES
                Siri / HA / ChatGPT / Claude
                           │
                           ▼
                      MCP / Assist
                           │
                           ▼
                    HOME ASSISTANT
                 estado + automatización
                           │
          ┌────────────────┼────────────────┐
          │                │                │
       Zigbee             MQTT        Integraciones
          │                │         LG / Samsung
          │                │
          │          EDGE SERVICES
          │                │
          │             Hailo-8
          │                │
          │       ┌────────┴────────┐
          │     visión         modelos AI
          │
          ▼
      mundo físico
```

------------------------------------------------------------------------

# 4. El repositorio empieza a parecer un producto

La organización por features es una decisión correcta:

``` text
packages/
├── tv
├── house_mode
├── paseo
├── seguridad
├── face
└── salud
```

Esto permite que una feature tenga agrupados:

-   helpers;
-   sensores;
-   automatizaciones;
-   scripts;
-   templates;
-   configuración relacionada.

También son señales de madurez:

``` text
Docker Compose Profiles
.env
secrets.yaml
health checks
deploy pull-only
runbooks
onboarding
backups
documentación de decisiones
```

El objetivo debería ser mantener esta dirección y evitar volver a una
configuración monolítica.

------------------------------------------------------------------------

# 5. El R2130 como appliance doméstico

La evolución hacia un único appliance basado en R2130 simplifica
considerablemente el sistema.

``` text
reComputer AI R2130
│
├── Home Assistant
├── Mosquitto
├── MCP
├── servicios auxiliares
├── Hailo-8
├── visión
└── NVMe
```

Ventajas:

-   menos equipos;
-   menos red interna entre componentes;
-   deployment más simple;
-   mantenimiento más simple;
-   menor consumo;
-   arquitectura replicable.

Pero introduce un riesgo:

``` text
R2130
=
Single Point of Failure
```

Por lo tanto, recuperación y observabilidad pasan a ser requisitos
arquitectónicos.

------------------------------------------------------------------------

# 6. Hailo ya dejó de ser experimental

El reconocimiento facial basado en:

``` text
SCRFD
  ↓
ArcFace
  ↓
embedding 512D
```

ejecutándose mediante Hailo demuestra que el patrón tecnológico
funciona:

``` text
Hailo inference
      ↓
servicio especializado
      ↓
MQTT
      ↓
Home Assistant
```

Esto valida la arquitectura para futuros modelos:

-   object detection;
-   person/dog;
-   pose;
-   clasificación de actividad;
-   segmentación;
-   CLIP;
-   modelos ONNX propios.

Ya no es necesario validar si Hailo puede participar de la arquitectura.

La pregunta pasa a ser:

``` text
¿Qué señales semánticas conviene producir?
```

------------------------------------------------------------------------

# 7. Evolución del reconocimiento facial

El modelo actual basado en captura periódica es válido como PoC.

Cuando Frigate esté incorporado, conviene migrar a un pipeline
event-driven.

## Actual

``` text
camera
  ↓
captura periódica
  ↓
FaceEmbed
  ↓
MQTT
```

## Objetivo

``` text
Frigate
   ↓
person detected
   ↓
zona relevante
   ↓
best snapshot / crop
   ↓
FaceEmbed
   ↓
known / unknown
   ↓
MQTT
```

Ventajas:

-   menor uso de CPU;
-   menor uso del Hailo;
-   menos capturas innecesarias;
-   menor competencia por la cámara;
-   mejor asociación entre evento y reconocimiento.

------------------------------------------------------------------------

# 8. Arquitectura Edge Vision objetivo

``` text
                    CAMERA
                       │
                      RTSP
                       │
                       ▼
                FRIGATE / YOLO
                       │
                    HAILO-8
                       │
         ┌─────────────┼─────────────┐
         │             │             │
        dog          person        event
         │             │             │
 dog classifier      pose          CLIP
         │             │             │
         └─────────────┼─────────────┘
                       │
                       ▼
                 VISION FUSION
                       │
                      MQTT
                       │
                       ▼
                HOME ASSISTANT
                       │
              ┌────────┴────────┐
              │                 │
       AUTOMATIONS             MCP
                                │
                                ▼
                              AGENT
```

------------------------------------------------------------------------

# 9. El siguiente objetivo de visión

No empezar por CLIP.

No empezar entrenando múltiples modelos.

Primero conseguir:

``` text
human_present
dog_present
```

con alta confiabilidad.

Éstas son dos de las señales más importantes de toda la plataforma.

Una vez estabilizadas, se pueden derivar:

``` text
owner_home
unknown_person
sofa_occupied
dog_activity
package_present
cleaning_activity
```

------------------------------------------------------------------------

# 10. Vision Fusion

No conviene que cada modelo tome decisiones sobre la casa.

Crear una capa intermedia:

``` text
vision-fusion
```

Inputs:

``` text
frigate/person
frigate/dog
face/identity
pose/person
dog/activity
clip/context
door/open
mmwave/presence
```

Output:

``` text
home/context
```

Ejemplo:

``` json
{
  "human_present": false,
  "dog": {
    "present": true,
    "room": "living",
    "activity": "sleeping"
  },
  "entrance": {
    "door": "closed",
    "package": false,
    "last_person": "18:14"
  }
}
```

------------------------------------------------------------------------

# 11. Tres capas de estado

Una mejora importante es separar tres conceptos.

## Percepción

Lo que los sensores observan:

``` text
owner_home
human_present
dog_present
lucas_visual
unknown_person
door_open
sofa_occupied
package_present
```

## Estado global

``` text
house_mode
├── HOME
├── AWAY
├── CLEANING
└── NIGHT
```

## Contextos

``` text
context
├── paseo
├── cinema
├── simulation
├── sleeping
└── guest
```

No convertir cada contexto en un nuevo `house_mode`.

------------------------------------------------------------------------

# 12. Flujo conceptual

``` text
                PERCEPTION
                    │
         ┌──────────┼──────────┐
        BLE       Zigbee     Vision AI
                    │
                    ▼
                 CONTEXT
                    │
                    ▼
                HOUSE STATE
                    │
                    ▼
              AUTOMATIONS
                    │
                    ▼
                 DEVICES
```

Esto permite mantener las automatizaciones deterministas aunque las
señales provengan de IA.

------------------------------------------------------------------------

# 13. MCP

La decisión correcta es mantener:

``` text
MCP
 ↓
Home Assistant
```

y no:

``` text
MCP
 ↓
hardware directamente
```

Home Assistant sigue siendo la capa de ejecución.

El MCP debería evolucionar hacia herramientas de dominio:

``` text
get_house_state()
get_presence()
get_dog_state()
get_security_context()
get_room_state(room)
activate_scene(scene)
set_house_mode(mode)
```

En lugar de exponer cientos de entidades individuales.

------------------------------------------------------------------------

# 14. MCP capability-based

El MCP no debería ser un acceso administrativo general a Home Assistant.

Exponer capacidades explícitas.

Ejemplos aceptables:

``` text
turn_on
turn_off
set_brightness
set_temperature
activate_scene
get_state
get_presence
set_house_mode
```

Evitar exponer directamente:

``` text
unlock
disable_alarm
admin_home_assistant
shell
arbitrary_service_call
```

Especialmente:

``` text
LLM
✗
unlock DDL615
```

La cerradura debe continuar siendo un sistema independiente de
autenticación.

------------------------------------------------------------------------

# 15. Hardening MCP

El endpoint MCP expuesto remotamente debe evolucionar hacia
autenticación robusta.

Si actualmente un `secret_path` funciona como bearer credential:

``` text
URL secreta
=
credencial
```

es conveniente migrar progresivamente a:

-   autenticación explícita;
-   tokens rotables;
-   OAuth cuando corresponda;
-   permisos mínimos;
-   capability allowlist;
-   logs de acceso;
-   rate limiting cuando sea práctico.

Cloudflare Tunnel puede seguir siendo el transporte, pero no debe ser la
única barrera lógica.

------------------------------------------------------------------------

# 16. Webhooks

Los webhook IDs deben tratarse como secretos.

Si un webhook:

``` text
local_only: false
```

puede ejecutar una acción, su ID equivale conceptualmente a una bearer
credential.

No mantener esos IDs versionados en Git.

Moverlos a:

``` text
secrets.yaml
```

o eliminar el mecanismo cuando MCP/HomeKit cubran el mismo caso.

Rotar los IDs existentes si estuvieron expuestos en repositorios
compartidos.

------------------------------------------------------------------------

# 17. Backup actual

El backup local protege contra errores operativos:

``` text
configuration.yaml roto
automatización incorrecta
cambio accidental
```

pero no contra:

``` text
NVMe muerto
corrupción completa
robo
falla física del R2130
```

Por lo tanto:

``` text
backup local
≠
disaster recovery
```

------------------------------------------------------------------------

# 18. Backup objetivo

Agregar backup cifrado off-device.

Arquitectura sugerida:

``` text
R2130
  │
  ├── backup local
  │
  └── restic
        │
        ├── NAS
        ├── S3 compatible
        ├── Backblaze B2
        └── otro storage externo
```

El backup debe contemplar:

``` text
Home Assistant config
.storage
Mosquitto
.env
secrets
Cloudflare config
face embeddings/database
custom services
Compose files
packages
```

Los backups externos deben estar cifrados.

------------------------------------------------------------------------

# 19. Recovery test

Un backup no está completo hasta haber probado restauración.

Crear un procedimiento:

``` text
fresh R2130 / host
 ↓
Docker
 ↓
restore repository
 ↓
restore secrets
 ↓
restore HA
 ↓
restore MQTT
 ↓
restore DB
 ↓
docker compose up
 ↓
health check
```

Objetivo:

``` text
RTO doméstico razonable:
< 1-2 horas
```

No es necesario automatizarlo completamente al principio, pero sí
documentarlo.

------------------------------------------------------------------------

# 20. Próximo cuello de botella: observabilidad

Con más servicios, el problema probablemente no será capacidad de
inferencia.

Será entender:

``` text
qué está consumiendo recursos
qué falló
por qué falló
cuándo empezó
```

Servicios futuros:

``` text
Home Assistant
Mosquitto
MCP
Frigate
go2rtc
Zigbee2MQTT
ESPHome
Music Assistant
FaceEmbed
vision-fusion
vision-dog
vision-pose
```

------------------------------------------------------------------------

# 21. Fase 3.5 --- Node Observability

Agregar antes de expandir Edge AI.

Métricas:

``` text
CPU %
RAM used
swap
load average

CPU temperature

NVMe usage
NVMe SMART
NVMe temperature
disk writes

Hailo temperature
Hailo utilization
inference latency

Docker container state
Docker memory/container
Docker CPU/container

Frigate FPS
detector latency
camera FPS

MQTT connected clients
MQTT availability
```

------------------------------------------------------------------------

# 22. Health monitoring

El health monitor actual puede evolucionar de:

``` text
HA OK?
MCP OK?
FaceEmbed OK?
```

a:

``` text
NODE
├── cpu
├── ram
├── temperature
├── nvme
└── network

SERVICES
├── HA
├── MQTT
├── MCP
├── Frigate
├── go2rtc
├── FaceEmbed
└── vision-fusion

AI
├── Hailo
├── detector latency
├── inference failures
└── camera availability
```

------------------------------------------------------------------------

# 23. Alertas

No alertar por cada métrica.

Crear alertas accionables:

``` text
disk > 85 %
temperature crítica
container restart loop
camera offline
MQTT offline
HA unavailable
Hailo unavailable
backup falló
backup demasiado antiguo
```

------------------------------------------------------------------------

# 24. Limitación de RAM

El nodo central debe administrarse como un appliance limitado.

La inferencia corre eficientemente en Hailo, pero:

``` text
Frigate
Home Assistant
Music Assistant
Python services
databases
MQTT
go2rtc
```

siguen consumiendo:

-   RAM;
-   CPU;
-   I/O;
-   page cache.

Por eso conviene medir antes de agregar servicios pesados.

------------------------------------------------------------------------

# 25. Zigbee y sensores físicos

Antes de aumentar complejidad de IA, incorporar sensores físicos
confiables:

``` text
sensor puerta
mmWave living
mmWave dormitorio opcional
Zigbee
```

Estos sensores son importantes porque proporcionan señales deterministas
que pueden fusionarse con visión.

Ejemplo:

``` text
door_open
+
person detected
+
owner away
=
evento de entrada
```

------------------------------------------------------------------------

# 26. Perro y ocupación humana

No utilizar:

``` text
motion = occupied
```

porque el perro puede generar movimiento.

Objetivo:

``` text
dog_present = true
human_present = false
```

sin cambiar:

``` text
house_mode = AWAY
```

Éste es uno de los casos donde Edge AI agrega valor real.

------------------------------------------------------------------------

# 27. CLEANING

El estado `CLEANING` puede inferirse combinando:

``` text
owner AWAY
+
cleaning schedule
+
door event
+
human_present
```

No es necesario que la cerradura informe qué PIN fue utilizado.

La DDL615 continúa gestionando autorización física.

Home Assistant interpreta contexto.

------------------------------------------------------------------------

# 28. DDL615

Mantener la separación:

``` text
Philips DDL615
→ ACCESS CONTROL

Home Assistant
→ CONTEXT + AUTOMATION

Vision AI
→ PERCEPTION
```

No usar reconocimiento facial ni geofence para desbloquear
automáticamente.

------------------------------------------------------------------------

# 29. Clasificador del perro

Después de estabilizar `dog_present`, el siguiente modelo custom útil
es:

``` text
MobileNetV3
```

Clases:

``` text
sleeping
standing
walking
eating
drinking
at_door
unknown
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
      ↓
MQTT
```

------------------------------------------------------------------------

# 30. Pose

Pose humana debe incorporarse después de person/dog.

Casos útiles:

``` text
standing
sitting
lying
sofa_occupied
```

Ejemplo:

``` text
person
+
sitting
+
sofa_zone
+
persistencia
=
sofa_occupied
```

Esto puede alimentar Modo Cine.

------------------------------------------------------------------------

# 31. CLIP

CLIP/TinyCLIP/MobileCLIP debe quedar detrás de modelos más baratos.

``` text
object detector
 ↓
evento interesante
 ↓
CLIP
```

Casos:

``` text
person cleaning
person carrying package
dog on sofa
dog at door
```

No utilizar CLIP como fuente única para acciones críticas.

------------------------------------------------------------------------

# 32. Cascade inference

Arquitectura recomendada:

``` text
                  FRAME
                    │
                    ▼
             OBJECT DETECTOR
                    │
          ┌─────────┴─────────┐
          │                   │
       person                dog
          │                   │
        pose           dog classifier
          │                   │
          └─────────┬─────────┘
                    │
             evento ambiguo?
                    │
                   YES
                    │
                    ▼
                   CLIP
```

Esto mantiene bajo el consumo y simplifica depuración.

------------------------------------------------------------------------

# 33. Estado semántico de la casa

El objetivo final no es que el agente lea entidades crudas.

Debe existir algo similar a:

``` json
{
  "mode": "AWAY",
  "owner": "away",
  "human_present": false,
  "dog": {
    "present": true,
    "room": "living",
    "activity": "sleeping"
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

------------------------------------------------------------------------

# 34. Preguntas de alto nivel

Con ese estado, el agente puede responder:

``` text
¿Qué pasa en casa?
```

``` text
¿Hay alguien?
```

``` text
¿Dónde está el perro?
```

``` text
¿Quedó algo prendido?
```

``` text
¿Está todo normal?
```

sin consultar manualmente decenas de entidades.

------------------------------------------------------------------------

# 35. Arquitectura objetivo

``` text
                           USER
                  ┌─────────┴─────────┐
                 Siri            ChatGPT/Claude
                  │                    │
                  │                   MCP
                  │                    │
                  └─────────┬──────────┘
                            ▼
                     HOME ASSISTANT
                            │
                   semantic house state
                            │
           ┌────────────────┼────────────────┐
           │                │                │
        Zigbee          ESPHome         Edge AI
           │                │                │
        sensors        IR / lights        Hailo
                                            │
                                  ┌─────────┼─────────┐
                                 YOLO     ArcFace   Pose
                                  │                   │
                                 dog                human
                                  │
                            custom classifier
                                  │
                          sleep/eat/walk/etc.
```

------------------------------------------------------------------------

# 36. Roadmap recomendado

## Prioridad 1 --- Hardening

Completar:

``` text
MCP auth
webhooks fuera de Git
rotación de secretos
backup cifrado off-device
recovery runbook
```

## Prioridad 2 --- Observabilidad

Agregar:

``` text
CPU
RAM
temperaturas
NVMe
Hailo
containers
Frigate
MQTT
backups
```

## Prioridad 3 --- Sensores físicos

``` text
Zigbee
sensor puerta
mmWave
```

## Prioridad 4 --- Frigate + Hailo

Primero:

``` text
person
dog
```

Nada más.

## Prioridad 5 --- Vision Fusion

Crear:

``` text
human_present
dog_present
```

de forma confiable.

## Prioridad 6 --- Face event-driven

Migrar:

``` text
captura periódica
→
Frigate event → FaceEmbed
```

## Prioridad 7 --- Pose

Crear:

``` text
sofa_occupied
```

y otros estados útiles.

## Prioridad 8 --- Dog classifier

Crear actividad semántica del perro.

## Prioridad 9 --- CLIP

Agregar contexto visual abierto.

------------------------------------------------------------------------

# 37. Lo que NO agregaría todavía

Evitar por ahora:

-   múltiples cámaras interiores;
-   múltiples modelos custom simultáneos;
-   VLM pesado;
-   LLM en Hailo-8;
-   reconocimiento facial como autenticación;
-   unlock mediante agentes;
-   Kubernetes;
-   observabilidad enterprise excesiva;
-   event bus complejo adicional a MQTT;
-   bases vectoriales sin caso de uso concreto.

El proyecto debe seguir siendo mantenible por una sola persona.

------------------------------------------------------------------------

# 38. Principios de arquitectura

## Local-first

``` text
Internet caído
≠
casa inutilizable
```

## Manual-first

``` text
Home Assistant caído
≠
interruptor deja de funcionar
```

## Deterministic-first

Acciones críticas deben depender de reglas deterministas.

## AI as perception

La IA observa y aporta contexto.

No reemplaza mecanismos de seguridad.

## Semantic interfaces

Los agentes consumen herramientas y estado de dominio.

No infraestructura cruda.

## Event-driven

Evitar polling innecesario cuando exista un evento natural.

## Observable

Todo servicio importante debe poder responder:

``` text
¿está vivo?
¿cuánto consume?
¿cuándo falló?
```

------------------------------------------------------------------------

# 39. Evaluación de la evolución

La evolución puede resumirse así:

``` text
DOMÓTICA
   ↓
HOME AUTOMATION PLATFORM
   ↓
EDGE AI HOME PLATFORM
   ↓
SEMANTIC HOME
```

El salto más importante será el último.

Una casa semántica no expone solamente:

``` text
binary_sensor.motion_1
binary_sensor.motion_2
media_player.tv
switch.light
```

Expone conceptos:

``` text
human_present
dog_sleeping
owner_away
cleaning_active
sofa_occupied
entrance_secure
house_healthy
```

Ésa es la capa que hace realmente útil al MCP y a los agentes.

------------------------------------------------------------------------

# 40. Objetivo final

La experiencia debería permitir preguntar:

``` text
¿Qué pasa en casa?
```

y obtener:

``` text
Estás fuera.

No hay personas detectadas.
El perro está en el living descansando.
La puerta está cerrada.
No hay paquetes en la entrada.
Las luces principales están apagadas.
Home Assistant, MQTT y visión están funcionando normalmente.
```

Sin enviar video a un proveedor externo.

Sin permitir que un LLM controle directamente mecanismos críticos.

Sin depender de Internet para que la casa funcione.

La arquitectura final sigue:

``` text
MUNDO FÍSICO
     ↓
PERCEPCIÓN
     ↓
CONTEXTO
     ↓
ESTADO
     ↓
AUTOMATIZACIONES
     ↓
ACCIONES
```

y, en paralelo:

``` text
ESTADO SEMÁNTICO
      ↓
     MCP
      ↓
    AGENTE
```

Ese es el norte arquitectónico del proyecto.
