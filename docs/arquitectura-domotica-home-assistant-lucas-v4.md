# Arquitectura domótica local-first --- Departamento / Single Occupant

**Versión:** 4.0\
**Contexto:** departamento, una sola persona, perro, limpieza periódica,
Philips DDL615, Home Assistant + Raspberry Pi 5 + Hailo-8

------------------------------------------------------------------------

# 1. Objetivo

Diseñar una casa automatizada que sea:

-   local-first;
-   simple;
-   confiable;
-   fácil de mantener;
-   ampliable;
-   independiente de una marca;
-   usable manualmente aunque Home Assistant falle.

La prioridad no es automatizar por automatizar.

La prioridad es mejorar:

1.  iluminación;
2.  climatización;
3.  TV/audio;
4.  presencia;
5.  seguridad;
6.  voz;
7.  consumo eléctrico.

------------------------------------------------------------------------

# 2. Arquitectura final recomendada

``` text
                         INTERNET
                            │
                      Router / Wi-Fi
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             │              │              │
       Home Assistant   Raspberry Pi 5    Zigbee
       Mini-PC / HAOS   + Hailo-8          │
             │              │              │
             │          Frigate/AI      sensores
             │          go2rtc          presencia
             │          audio           puerta
             │                           temp.
             │
             ├── LG OLED C5 ─────── LAN / webOS
             │
             ├── Shelly ─────────── luces / dimmers
             │
             ├── ESPHome IR ─────── NAD + aire
             │
             └── Voice Assist
```

No hace falta un despliegue grande de infraestructura.

Para un departamento de una sola persona:

-   no hacen falta muchas cámaras;
-   no hace falta un switch PoE grande inicialmente;
-   no hace falta una VLAN compleja desde el día uno;
-   no hacen falta sensores en cada metro cuadrado;
-   no hacen falta hubs propietarios por marca.

------------------------------------------------------------------------

# 3. Distribución de responsabilidades

## Home Assistant

Corre en el mini-PC.

Responsabilidades:

-   automatizaciones;
-   escenas;
-   dashboards;
-   lógica de presencia;
-   control de luces;
-   control de TV;
-   control de aire;
-   control del NAD;
-   sensores;
-   voz;
-   Music Assistant;
-   MQTT.

``` text
Mini-PC
└── Home Assistant OS
    ├── Shelly
    ├── Zigbee
    ├── LG webOS
    ├── ESPHome
    ├── Frigate integration
    ├── Music Assistant
    └── Assist / Voice
```

------------------------------------------------------------------------

# 4. Raspberry Pi 5 + Hailo-8

La Raspberry no será el cerebro de la casa.

Será un **nodo edge AI**.

``` text
Raspberry Pi 5
├── Raspberry Pi OS 64-bit
├── Docker
├── Frigate
├── Hailo-8 26 TOPS
├── go2rtc
├── Squeezelite
└── servicios AI propios
```

El Hailo-8 queda sobrado para una o dos cámaras, lo cual es positivo.

Se puede aprovechar también para:

-   detección de personas;
-   animales;
-   paquetes;
-   clasificación;
-   segmentación;
-   pose estimation;
-   modelos propios;
-   servicios Python/Go;
-   eventos MQTT hacia Home Assistant.

------------------------------------------------------------------------

# 5. Cámaras: mínimo necesario

No llenaría el departamento de cámaras.

## Recomendación

Una cámara en:

``` text
entrada
o
balcón
```

Sólo agregaría una segunda cámara si aparece una necesidad concreta.

Ejemplo:

``` text
Cámara entrada
      │
      ▼
   Frigate
      │
      ▼
   Hailo-8
      │
      ├── persona
      ├── paquete
      ├── animal
      └── movimiento relevante
             │
             ▼
       Home Assistant
```

Para interiores prefiero sensores de presencia antes que cámaras.

------------------------------------------------------------------------

# 6. Presencia

Este es uno de los componentes más importantes de toda la arquitectura.

Como vive una sola persona, Home Assistant puede asumir reglas mucho más
simples.

## Capas de presencia

### Nivel 1 --- presencia en casa

Teléfono:

``` text
Lucas HOME
Lucas AWAY
```

Esto alcanza para saber si el departamento está ocupado.

------------------------------------------------------------------------

### Nivel 2 --- presencia por habitación

Usar mmWave.

Ejemplo:

``` text
Living
└── sensor presencia mmWave

Dormitorio
└── sensor presencia mmWave
```

Para el living recomiendo:

**Everything Presence Pro**

Funciones:

-   mmWave;
-   presencia estática;
-   múltiples targets;
-   zonas;
-   PIR;
-   temperatura;
-   humedad;
-   luminosidad;
-   ESPHome;
-   Ethernet/PoE;
-   Bluetooth Proxy.

Ejemplo:

``` text
LIVING

┌─────────────────────────────┐
│                             │
│ SOFÁ          MESA          │
│ zone_1        zone_2        │
│                             │
│           TV                │
│           zone_3            │
└─────────────────────────────┘
```

Esto permite detectar:

``` text
presencia en sofá
+
TV encendida
=
modo cine
```

------------------------------------------------------------------------

# 7. Sensor de puerta

Agregar un sensor Zigbee simple en la puerta de entrada.

Permite:

``` text
puerta abierta
      +
teléfono acaba de llegar
      ↓
evento "llegada"
```

o:

``` text
puerta abierta
      +
teléfono AWAY
      ↓
alerta
```

------------------------------------------------------------------------

# 8. Zigbee

En un departamento no hace falta una red enorme.

Un coordinador bien ubicado debería alcanzar.

## Opción simple

**Home Assistant Connect ZBT-2**

``` text
Home Assistant
      │
     USB
      │
      ▼
    ZBT-2
      │
      ├── presencia
      ├── puerta
      ├── temp/humedad
      ├── botones
      └── fuga de agua
```

## Opción premium

**SMLIGHT SLZB-MR4U**

Tiene sentido si se valora:

-   Ethernet;
-   PoE;
-   posición independiente del servidor;
-   Zigbee + Thread simultáneo;
-   radios separados.

Pero no es obligatorio en un departamento pequeño.

------------------------------------------------------------------------

# 9. Thread / Matter

No forzaría Matter.

Regla:

``` text
si Zigbee funciona bien
→ usar Zigbee

si un producto Matter/Thread es claramente mejor
→ usar Matter/Thread
```

No comprar dispositivos sólo porque digan "Matter".

------------------------------------------------------------------------

# 10. Iluminación ON/OFF

Para una luz común:

``` text
             220 V
               │
          ┌────▼─────┐
tecla ───►│ Shelly   │
          │ 1PM      │
          └────┬─────┘
               │
               ▼
        lámpara normal
```

La tecla física sigue funcionando.

Home Assistant puede controlar el mismo circuito.

``` text
tecla física ───┐
                ▼
             Shelly ───► luz
                ▲
                │
        Home Assistant
```

------------------------------------------------------------------------

# 11. Luz regulable

Para controlar brillo:

``` text
Shelly Dimmer Gen3
        +
LED DIMMABLE
```

No hace falta una bombita inteligente.

Ejemplo:

``` text
Pulsador
   │
   ▼
Shelly Dimmer Gen3
   │
   ▼
LED dimmable
```

Home Assistant:

``` yaml
action: light.turn_on
target:
  entity_id: light.living
data:
  brightness_pct: 15
  transition: 2
```

------------------------------------------------------------------------

# 12. ¿Qué significa "LED dimmable"?

La lámpara debe indicar:

-   DIMMABLE;
-   REGULABLE;
-   DIMERIZABLE.

No usar LED común no regulable con dimmer.

Problemas posibles:

-   parpadeo;
-   zumbido;
-   apagado bajo cierto porcentaje;
-   inestabilidad;
-   daño del driver.

------------------------------------------------------------------------

# 13. Pulsadores

Para luces regulables prefiero pulsadores momentáneos.

``` text
click
→ ON/OFF

mantener
→ subir/bajar brillo

doble click
→ escena opcional
```

Ejemplo:

``` text
click
→ luz

doble click
→ modo cine

long press
→ dimming
```

------------------------------------------------------------------------

# 14. Smart bulbs

Usarlas sólo cuando aporten algo real.

Casos:

-   RGB;
-   temperatura de color;
-   escenas;
-   varias lámparas individuales en el mismo circuito.

``` text
220 V permanente
      │
      ▼
smart bulb
      ▲
      │ Zigbee
      ▼
Home Assistant
```

No cortar alimentación a una smart bulb con una tecla convencional.

------------------------------------------------------------------------

# 15. Enchufes

No llenaría el departamento de smart plugs.

Sólo automatizar donde haya beneficio concreto.

Ejemplos:

-   lámpara de pie;
-   ventilador;
-   cafetera;
-   impresora;
-   cargadores;
-   algún equipo que se quiera medir.

Para instalación fija:

``` text
220 V
 │
Shelly 1PM
 │
tomacorriente
```

------------------------------------------------------------------------

# 16. Equipos a los que NO cortaría alimentación

No usar smart plug como método normal de apagado para:

-   LG OLED;
-   NAD;
-   aire acondicionado;
-   computadoras;
-   router;
-   Raspberry Pi.

Usar siempre su protocolo normal.

------------------------------------------------------------------------

# 17. LG OLED55C5PSA

Integración directa:

``` text
Home Assistant
      │
     LAN
      │
      ▼
LG OLED C5
```

Funciones:

-   Power;
-   volumen;
-   mute;
-   HDMI;
-   apps;
-   estado;
-   Wake-on-LAN.

No usar IR salvo fallback.

------------------------------------------------------------------------

# 18. NAD D 3020 V2

Controlarlo con ESPHome IR.

``` text
Home Assistant
      │
   ESPHome
      │
    ESP32
      │
IR transistor / MOSFET
      │
LED IR 940 nm
      │
      ▼
NAD D3020 V2
```

Comandos:

-   Power ON;
-   Power OFF;
-   Volume +;
-   Volume -;
-   Mute;
-   Source;
-   Bass;
-   Dim.

------------------------------------------------------------------------

# 19. TV Connect

La LG queda conectada por óptico al NAD:

``` text
LG OLED
   │
 Optical
   │
   ▼
NAD D3020 V2
```

Objetivo:

``` text
LG ON
↓
audio óptico
↓
NAD despierta
↓
Optical
```

El IR de ESPHome queda como control avanzado y fallback.

------------------------------------------------------------------------

# 20. Aire acondicionado

Orden de preferencia:

``` text
API local
   ↓
si no
   ↓
ESPHome IR
```

Ejemplo:

``` text
Home Assistant
      │
      ▼
 ESP32 IR
      │
      ▼
 Aire
```

Agregar sensor independiente de temperatura.

No depender de la temperatura interna del aire.

------------------------------------------------------------------------

# 21. Automatización de llegada

Como vive una sola persona, esta automatización puede ser muy confiable.

``` text
teléfono cambia a HOME
       +
puerta entrada se abre
       ↓
LLEGADA
       │
       ├── si es de noche → living 30 %
       ├── si temp > 27 °C → aire
       └── actualizar estado casa
```

------------------------------------------------------------------------

# 22. Automatización de salida

Especialmente útil para una sola persona.

``` text
teléfono pasa a AWAY
       +
no hay presencia mmWave
       ↓
CASA VACÍA
       │
       ├── apagar luces
       ├── apagar aire
       ├── apagar TV
       ├── apagar NAD
       └── activar alertas
```

No existe el riesgo habitual de apagarle cosas a otra persona que quedó
en casa.

------------------------------------------------------------------------

# 23. Modo cine

``` text
presencia en sofá
      +
LG encendida
      +
luminosidad baja
      ↓
MODO CINE
      │
      ├── living 15 %
      ├── NAD ON
      ├── NAD Optical
      └── si temp > 26 °C
              ↓
           aire 24 °C
```

Ejemplo:

``` yaml
alias: Modo Cine

triggers:
  - trigger: state
    entity_id: binary_sensor.sofa_occupied
    to: "on"

conditions:
  - condition: state
    entity_id: media_player.lg_oled_c5
    state: "on"

actions:
  - action: light.turn_on
    target:
      entity_id: light.living
    data:
      brightness_pct: 15
      transition: 2

  - action: button.press
    target:
      entity_id: button.nad_power_on

  - if:
      - condition: numeric_state
        entity_id: sensor.temperatura_living
        above: 26
    then:
      - action: climate.set_temperature
        target:
          entity_id: climate.aire_living
        data:
          temperature: 24
```

------------------------------------------------------------------------

# 24. Modo noche

Ejemplo:

``` text
hora > 23:00
      +
presencia dormitorio
      +
living vacío
      ↓
MODO NOCHE
      │
      ├── living OFF
      ├── TV OFF
      ├── NAD OFF
      ├── luces pasillo 5 %
      └── aire dormitorio según temperatura
```

------------------------------------------------------------------------

# 25. Modo despertar

``` text
hora definida
      +
día laborable
      ↓
DESPERTAR
      │
      ├── luz 10 %
      ├── luego 30 %
      ├── temperatura confortable
      └── música/radio opcional
```

------------------------------------------------------------------------

# 26. Home Assistant Voice

Tiene mucho sentido viviendo solo.

Un dispositivo en el living puede cubrir gran parte del departamento
dependiendo de la distribución.

Comandos:

``` text
"apagá todo"

"modo cine"

"poné el living al 15 %"

"prendé el aire a 24"

"poné música"

"apagá la tele"
```

Recomendación:

**Home Assistant Voice Preview Edition**

Empezaría con uno.

------------------------------------------------------------------------

# 27. Audio con Raspberry + NAD

El NAD D3020 V2 no tiene entrada USB de audio.

La Raspberry puede funcionar como endpoint de Music Assistant usando:

``` text
Raspberry Pi
    │ USB
    ▼
USB → S/PDIF
    │ coaxial
    ▼
NAD
```

Mientras:

``` text
LG OLED
   │ optical
   ▼
NAD
```

Arquitectura:

``` text
Music Assistant
(Home Assistant)
      │
      ▼
Squeezelite
(Raspberry Pi)
      │
USB → S/PDIF
      │
      ▼
NAD coaxial
```

------------------------------------------------------------------------

# 28. Raspberry: software interesante

## Sí

### Frigate

Uso principal del Hailo.

### go2rtc

Streaming y cámaras.

### Squeezelite

Endpoint de audio.

### Servicios propios

Puede correr microservicios para:

-   detección;
-   clasificación;
-   MQTT;
-   visión;
-   automatizaciones custom;
-   análisis de cámaras.

------------------------------------------------------------------------

## Opcional

### Node-RED

Útil para flujos complejos.

No obligatorio.

Home Assistant ya cubre la mayoría de automatizaciones.

### Scrypted

Interesante si luego se quiere integrar fuerte con Apple Home.

### Bluetooth Proxy

Mejor distribuir ESP32 pequeños que depender de la Pi como proxy BLE
central.

------------------------------------------------------------------------

# 29. SSD para la Raspberry

No usar microSD para Frigate 24/7.

``` text
Pi 5
├── PCIe → Hailo-8
└── USB 3 → SSD
```

Recomendación:

-   1 TB si se usa una cámara;
-   2 TB si se agregan más cámaras o más retención.

------------------------------------------------------------------------

# 30. Refrigeración Raspberry

Comprar:

-   Raspberry Pi Active Cooler;
-   buen gabinete;
-   fuente oficial;
-   SSD USB;
-   Ethernet.

La Raspberry quedará 24/7.

------------------------------------------------------------------------

# 31. BOM --- imprescindible

## Infraestructura

    Cant. Producto
  ------- -------------------------------------
        1 Home Assistant en mini-PC existente
        1 coordinador Zigbee
        1 Raspberry Pi Active Cooler
        1 SSD USB 1 TB
        1 fuente estable para Raspberry Pi 5

## Living

    Cant. Producto
  ------- -------------------------------
        1 Shelly Dimmer Gen3
        1 LED dimmable de calidad
        1 sensor presencia mmWave
        1 sensor temp/humedad
        1 ESP32
        1 emisor IR + transistor/MOSFET
        1 receptor IR opcional

## Entrada

    Cant. Producto
  ------- ------------------------
        1 sensor apertura Zigbee

------------------------------------------------------------------------

# 32. BOM --- recomendable

    Cant. Producto
  ------- ---------------------------
        1 Home Assistant Voice PE
        1 Everything Presence Pro
        1 cámara PoE entrada/balcón
        1 UPS pequeña
        1 USB → S/PDIF para NAD

------------------------------------------------------------------------

# 33. BOM --- opcional

    Cant. Producto
  ------- ------------------------------
        1 segunda cámara
        1 sensor presencia dormitorio
        1 sensor fuga agua cocina
        1 sensor fuga agua baño
      1-2 Shelly 1PM adicionales
        1 sensor CO₂
        1 sensor luminosidad adicional

------------------------------------------------------------------------

# 34. Qué comprar en USA

Aprovecharía principalmente productos que tengan mejor disponibilidad o
precio allá.

## Alta prioridad

1.  Home Assistant Voice Preview Edition.
2.  Everything Presence Pro.
3.  SSD USB de buena calidad.
4.  Active Cooler.
5.  ESP32 y componentes IR.
6.  USB → S/PDIF.
7.  cámara Reolink PoE.

## Según disponibilidad/precio

8.  Home Assistant Connect ZBT-2.
9.  SMLIGHT SLZB-MR4U.
10. sensores Zigbee Aqara.
11. Shelly.

------------------------------------------------------------------------

# 35. Qué NO comprar

No compraría por ahora:

-   Google Coral;
-   múltiples hubs propietarios;
-   gran switch PoE;
-   5 o 6 cámaras;
-   múltiples Voice PE;
-   sensores en todas las habitaciones;
-   smart plugs por todos lados;
-   cámaras cloud-only;
-   dispositivos Matter sin necesidad.

------------------------------------------------------------------------

# 36. Prioridad de implementación

## Fase 1 --- Living

1.  Home Assistant.
2.  LG webOS.
3.  Shelly Dimmer.
4.  LED dimmable.
5.  sensor presencia.
6.  sensor temperatura.
7.  ESPHome IR.
8.  NAD.
9.  aire.
10. Modo Cine.

------------------------------------------------------------------------

## Fase 2 --- Presencia casa

1.  Zigbee.
2.  sensor puerta.
3.  tracking del teléfono.
4.  automatización llegada.
5.  automatización salida.
6.  Modo Noche.

------------------------------------------------------------------------

## Fase 3 --- Raspberry

1.  Active Cooler.
2.  SSD.
3.  Raspberry Pi OS.
4.  Docker.
5.  Hailo.
6.  Frigate.
7.  una cámara.
8.  integración con Home Assistant.

------------------------------------------------------------------------

## Fase 4 --- Voz y audio

1.  Home Assistant Voice.
2.  Music Assistant.
3.  Squeezelite.
4.  USB-S/PDIF.
5.  integración NAD.

------------------------------------------------------------------------

# 37. Arquitectura final resumida

``` text
                         DEPARTAMENTO
                              │
                      Home Assistant
                        mini-PC / HAOS
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
        Shelly              Zigbee             ESPHome
          │                   │                   │
       luces            presencia/puerta         IR
       dimmers           temperatura             │
                                                ├── NAD
                                                └── Aire

LG OLED ───────────── LAN / webOS
   │
 optical
   ▼
NAD D3020 V2

Raspberry Pi 5 + Hailo-8
   │
   ├── Frigate
   ├── 1 cámara
   ├── go2rtc
   ├── Squeezelite
   └── Edge AI
```

------------------------------------------------------------------------

# 38. Regla de diseño

Para cada nuevo dispositivo:

``` text
¿Existe API local?
      ↓ sí
usar API local

      ↓ no
¿Zigbee/Matter?
      ↓ sí
usar Zigbee/Matter

      ↓ no
¿ESPHome?
      ↓ sí
usar ESPHome

      ↓ no
IR/RF

Cloud
→ último recurso
```

------------------------------------------------------------------------

# 39. Resumen ejecutivo

Para un departamento de una sola persona, la arquitectura óptima es:

``` text
Home Assistant
+
2 sensores de presencia como máximo
+
1 sensor puerta
+
Shelly en luces importantes
+
1 ESP32 IR
+
LG por LAN
+
NAD por IR/Optical
+
aire por IR/API
+
1 cámara como máximo al principio
+
Raspberry Pi 5 + Hailo como edge AI
+
Voice Assist
```

Eso cubre prácticamente todas las automatizaciones útiles sin convertir
el departamento en un laboratorio sobredimensionado.

La prioridad es:

``` text
presencia
→ iluminación
→ clima
→ entretenimiento
→ voz
→ seguridad
→ AI
```

------------------------------------------------------------------------

# 40. Seguridad eléctrica

Todos los módulos Shelly empotrados trabajan con tensión de red.

La instalación debe ser realizada o revisada por un electricista.

Antes de comprar múltiples módulos conviene relevar:

-   fase;
-   neutro;
-   retorno;
-   profundidad de cajas;
-   potencia;
-   tipo de carga;
-   estado del cableado.

------------------------------------------------------------------------

# 41. Ocupación real: propietario + perro + limpieza

La lógica no debe reducirse a `HOME/AWAY`. Hay que distinguir:

``` text
owner_home
human_present
dog_present
door_open
cleaning_window
```

Estados globales: `HOME`, `AWAY`, `CLEANING` y `NIGHT`. `CINEMA` queda
como escena.

El perro puede generar movimiento sin ocupación humana; además, la
persona de limpieza puede estar legítimamente dentro mientras el
propietario está `AWAY`.

# 42. Philips DDL615-5HBS

Modelo: **Philips 6000 Series DDL615-5HBS / DDL615LIPKB/00**.

La documentación oficial confirma Home Access, configuración por
Bluetooth, huella, PIN, key tag, llave mecánica, PIN offline, PIN
recurrente, PIN limitado por tiempo y doble verificación.

## Resultado de la investigación

A septiembre de 2026 **no hay evidencia suficiente de una integración
directa DDL615 ↔ Home Assistant**.

El manual describe Bluetooth y no documenta Wi-Fi integrado, gateway
Wi-Fi compatible, Matter, Thread, Zigbee ni API local.

Hay otras cerraduras Philips Home Access con Wi-Fi/bridge, pero no se
debe extrapolar esa compatibilidad a DDL615.

# 43. No comprar gateway Philips todavía

Existen dos integraciones comunitarias relevantes, pero ninguna confirma
DDL615.

`rsheptolut/philips-home-access` está basada en ingeniería inversa de
cerraduras Home Access Kaadas/iRevo sobre Juzi Wulian/Oneness. Su
roadmap deja BLE local como trabajo futuro.

La DDL615 está documentada como producto de **Shenzhen Conex Intelligent
Technology Co., Ltd.** y la app Android `com.conex.philips` también
pertenece a Conex.

`rjbogz/philips_home_access` está orientada a cerraduras Wi-Fi y
cerraduras mediante gateway, con soporte probado sólo en una cantidad
limitada de modelos.

Decisión:

``` text
Philips Wi-Fi gateway
→ NO comprar por ahora

ESP32 Bluetooth Proxy sólo para DDL615
→ NO comprar con ese objetivo
```

Un Bluetooth Proxy puede seguir siendo útil para otros dispositivos BLE.

# 44. PIN offline y acceso de limpieza

La DDL615 permite generar desde la app PIN de un solo uso, recurrentes y
limitados por tiempo. Que el PIN pueda generarse remotamente **no
significa que la cerradura esté online**: la validación puede realizarse
localmente.

Para limpieza:

``` text
Nombre: Limpieza
Tipo: PIN recurrente

Ejemplo:
martes
09:00 → 14:00
```

No compartir PIN maestro, cuenta Philips principal ni credenciales Home
Assistant.

# 45. Sensor de puerta independiente

Mientras DDL615 no esté integrada, Home Assistant no debe depender de
ella para saber quién entró o si la puerta está abierta.

Agregar un sensor Zigbee:

``` text
DDL615
  └── seguridad/autorización física

Sensor Zigbee
  └── open / closed
          │
          ▼
    Home Assistant
```

Regla:

``` text
DDL615 → controla ACCESO
Home Assistant → controla CONTEXTO
```

# 46. Presencia con perro

No usar `PIR = HOME`.

Para iluminación, PIR/mmWave es suficiente. Para ocupación humana
combinar:

``` text
iPhone
+
sensor puerta
+
mmWave
+
Frigate person/dog
```

El perro puede producir `dog_present` sin cambiar la casa a `HOME`.

# 47. Frigate + Hailo: person versus dog

Una sola cámara bien ubicada en la zona de entrada puede aportar:

``` text
camera
  ↓
Frigate
  ↓
Hailo-8
  ├── person
  └── dog
```

No necesitamos reconocimiento facial. Sólo distinguir presencia humana
de presencia del perro.

Evitar múltiples cámaras interiores salvo necesidad concreta.

# 48. Modo CLEANING

Como HA no recibe el PIN utilizado en DDL615, no inventar un evento
`PIN limpieza utilizado`.

Inferir:

``` text
Lucas AWAY
+
schedule.limpieza = ON
+
puerta se abre
+
human_present = true
↓
CLEANING
```

Ejemplo conceptual:

``` yaml
alias: Entrar en modo limpieza

triggers:
  - trigger: state
    entity_id: binary_sensor.puerta_entrada
    to: "on"

conditions:
  - condition: state
    entity_id: person.lucas
    state: "not_home"

  - condition: state
    entity_id: schedule.limpieza
    state: "on"

  - condition: state
    entity_id: binary_sensor.human_present
    state: "on"

actions:
  - action: input_select.select_option
    target:
      entity_id: input_select.house_mode
    data:
      option: CLEANING
```

Agregar delays/timeouts en producción para evitar carreras entre puerta
y presencia.

# 49. Comportamiento CLEANING

``` text
✓ luces automáticas
✓ iluminación fuerte para limpiar
✓ climatización si hace falta
✓ no disparar alertas normales

✗ Modo Cine automático
✗ TV automática
✗ NAD automático
✗ escenas personales
```

Salida:

``` text
Lucas sigue AWAY
+
puerta cerrada
+
human_present = false durante N minutos
↓
AWAY
```

Entonces apagar luces, aire, TV/NAD y volver a seguridad normal.

# 50. HOME / AWAY corregidos

HOME:

``` text
iPhone Lucas → HOME
+
puerta abierta recientemente (confirmación opcional)
=
HOME
```

AWAY:

``` text
iPhone AWAY
+
human_present = false
+
CLEANING = false
=
AWAY
```

No apagar todo inmediatamente ante un único cambio de geofence.

# 51. Seguridad de la cerradura

Aunque aparezca una integración futura:

``` text
sensores → luces/escenas/notificaciones
sensores ✗ → unlock automático
```

No desbloquear automáticamente sólo por geofence, cámara o presencia.

Si luego se integra lock/unlock: MFA, acceso remoto protegido, permisos
mínimos y llave mecánica de emergencia fuera del departamento.

# 52. DDL615 como proyecto BLE experimental

Puede investigarse:

``` text
Philips Home Access
com.conex.philips
        ↓
BLE reverse engineering
        ├── GATT services
        ├── characteristics
        ├── handshake
        ├── autenticación
        ├── cifrado
        └── eventos
        ↓
prototipo Python
        ↓
integración Home Assistant
```

Hasta tener una implementación probada:

``` text
DDL615 → autónoma
HA → observa contexto
```

# 53. BOM actualizado

    Cant. Producto                             Uso
  ------- ------------------------------------ -----------------------------
        1 sensor Zigbee puerta/ventana         estado real de puerta
        1 mmWave living                        presencia/contexto
        1 mmWave dormitorio opcional           presencia por ambiente
        1 cámara RTSP/ONVIF entrada opcional   `person` vs `dog` con Hailo

No comprar por ahora:

  Producto                       Decisión
  ------------------------------ -------------------------------------
  Philips Wi-Fi gateway          compatibilidad DDL615 no confirmada
  ESP32 dedicado sólo a DDL615   integración BLE no confirmada
  Google Coral                   Hailo-8 ya cubre inferencia
  múltiples cámaras interiores   innecesarias

# 54. Arquitectura de ocupación definitiva

``` text
                         DEPARTAMENTO
                              │
                      Home Assistant
                              │
       ┌──────────────────────┼───────────────────────┐
       │                      │                       │
    iPhone                 Zigbee                Frigate
       │                ┌─────┴─────┐             + Hailo
       │                │           │                │
    Lucas             puerta      mmWave         person/dog
  home/away          open/close   presencia          │
       └────────────────┴─────┬─────┴────────────────┘
                              │
                              ▼
                         HOUSE MODE
                    HOME / AWAY / CLEANING

Philips DDL615
      ├── credencial propietario
      └── PIN recurrente limpieza
```

# 55. Referencias DDL615 / Home Assistant

-   Philips DDL615: https://www.philips.com.ar/c-p/DDL615LIPKB_00/
-   Manual DDL615:
    https://manuals.plus/m/c61519e1506d90a45b412724b4fefed98d27b8f6c315119d9fb3cf1f57fcdf31.pdf
-   Philips Home Access / Conex:
    https://play.google.com/store/apps/details?id=com.conex.philips
-   HACS Kaadas/iRevo: https://github.com/rsheptolut/philips-home-access
-   Integración comunitaria Wi-Fi:
    https://github.com/rjbogz/philips_home_access
