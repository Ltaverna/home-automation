# NeuralCore Home — El cerebro privado de tu casa
### Propuesta comercial · domótica local-first con IA en el borde

> *Nombre de trabajo: NeuralCore Home (sobre el dominio `neuralcore.dev`).*
> *Documento comercial — v1, 2026-10-10.*

---

## 1. El problema que nadie resolvió bien

La "casa inteligente" de hoy está rota:

- **Depende de la nube.** Se cae tu internet (o el servidor de Amazon/Google) y tu casa se vuelve tonta. Las luces, el termostato, las cámaras: todo deja de responder.
- **Te espía.** Alexa/Google escuchan y mandan todo a la nube. En una casa — dormitorios, rutinas, quién entra y sale — eso es tu vida entera en servidores ajenos.
- **Está fragmentada.** Una app para la TV, otra para las luces, otra para la cámara. Nada se entiende entre sí.
- **Es reactiva, no inteligente.** Responde a comandos ("prendé la luz"), pero no *entiende* la casa: no sabe si hay alguien, si es el perro, si saliste.

La gente que puede pagar una buena casa **no quiere** otro gadget que la espíe y se cuelgue.

---

## 2. La solución

**Un solo equipo, del tamaño de un libro, que es el cerebro privado de la casa.**

Corre **todo localmente** sobre un nodo con acelerador de IA (NPU). Sin nube obligatoria, sin suscripción para que funcione lo básico, sin que tus datos salgan de tu casa.

```
   ┌──────────────────────────────────────────────┐
   │   NeuralCore Home  ·  un nodo edge con IA      │
   │                                                │
   │   Percepción  →  Entendimiento  →  Acción      │
   │   (sensores,     (estado          (luces, TV,  │
   │    cámara,        semántico         clima,      │
   │    presencia)     con IA local)     seguridad)  │
   │                                                │
   │   Control:  Voz (Siri) · App · Agente IA        │
   └──────────────────────────────────────────────┘
          Privado · Offline-first · Inteligente
```

**Tres promesas:**
1. **Privado de verdad** — la IA corre en el borde, en tu casa. Nada se sube a la nube.
2. **Funciona aunque se caiga internet** — la lógica crítica es local; los interruptores físicos siguen andando.
3. **Entiende tu casa** — no ejecuta comandos sueltos; construye un *estado semántico* ("nadie en casa, el perro está en el living, la puerta cerrada") y actúa sobre eso.

---

## 3. El producto: qué hace HOY (no es una promesa)

Esto ya está construido, funcionando y en producción en una casa real:

| Capacidad | Qué significa para el cliente |
|---|---|
| **Control unificado de TVs** | Encendido, apps (Netflix/YouTube/streaming), canales y volumen de todas las TVs desde un lugar — por voz, app o un toque. |
| **Voz nativa (Siri/Apple Home)** | "Oye Siri, modo cine" / "prendé Netflix en el dormitorio". Sin hub extra. |
| **Control por Inteligencia Artificial** | Hablarle a un asistente (Claude/ChatGPT) y que controle la casa: *"¿está todo apagado?"*, *"prepará la casa para dormir"*. Único en el mercado residencial. |
| **Modos de casa** | HOME / AWAY / NOCHE / LIMPIEZA: la casa se adapta sola (apaga TVs al salir, baja todo de noche). |
| **Presencia por geolocalización** | Sabe cuándo llegás o salís (celular) y actúa: apaga todo al irte, te avisa. |
| **Seguridad y simulación de presencia** | Modo anti-robo: simula que hay alguien (prende/apaga TVs al azar) cuando no estás. |
| **Reconocimiento facial en el borde (IA)** | Identifica personas con el acelerador Hailo — **sin mandar la cara a ninguna nube**. |
| **Cuidado de mascota** | Modo paseo del perro, lógica que distingue al perro de una persona (en evolución con visión). |
| **Confiabilidad "de grado industrial"** | Backups cifrados fuera del sitio, monitoreo de salud del sistema con alertas, recuperación ante desastres probada. Esto no es un proyecto de hobby: tiene la robustez de un producto. |

**El diferencial que vende solo:** *tu casa controlada por un agente de IA, con todo corriendo en una caja privada en tu placard.* Eso hoy no lo ofrece Amazon, Google ni Apple.

---

## 4. Escenas que se venden (demos de 30 segundos)

- **"Llegué."** El auto entra al barrio → el portón, luces de entrada y clima se preparan solos.
- **"Modo cine."** Un comando → TV en la app, luces al 10%, sonido al receiver, persianas abajo.
- **"Salí."** Nadie en casa → todo se apaga, seguridad activa, simulación de presencia a la noche.
- **"¿Qué pasa en casa?"** Le preguntás al asistente desde el trabajo y responde: *"Nadie en casa, el perro está en el living, la puerta cerrada, todo normal."*
- **"Buenas noches."** Un comando apaga todo, baja el clima, arma la alarma suave y deja la luz de pasillo tenue.

---

## 5. Por qué nosotros (y por qué ahora)

- **Ya está construido y probado** — no vendemos una idea, mostramos un producto funcionando.
- **Arquitectura replicable** — el sistema está diseñado para instalarse en una casa nueva con un proceso de onboarding documentado. Lo que aprendimos en la primera casa se replica.
- **IA en el borde, de verdad** — usamos un NPU dedicado (Hailo, 26 TOPS) para visión/reconocimiento local. La mayoría "hace IA" mandando todo a la nube; nosotros no.
- **Local-first como principio de diseño** — privacidad y resiliencia no son un extra, son la base.
- **Abierto y sin lock-in** — construido sobre estándares abiertos (Home Assistant, MQTT, Matter/Zigbee), no sobre un ecosistema cerrado que te secuestra.

---

## 6. El plan — roadmap del producto

```
FASE 1  ✅  BASE               Nodo + control de TVs + voz + modos + presencia + backups
FASE 2  🔜  PRESENCIA FÍSICA   Sensores Zigbee (puerta, movimiento mmWave) → "hay alguien" confiable
FASE 3  🔜  VISIÓN             Cámara + Frigate + Hailo → detección persona/perro, zonas
FASE 4  🔜  HOGAR SEMÁNTICO    Fusión de señales → estado único de la casa que la IA entiende
FASE 5  🔜  HOGAR AGÉNTICO     El asistente razona sobre el estado: seguridad, confort, rutinas
```

- **Fase 1 — Base (hecha):** el producto que se describe arriba, en producción.
- **Fase 2 — Presencia física:** sensores de puerta y movimiento por radar (mmWave) para saber con certeza si hay alguien, sin cámara. Habilita automatizaciones de verdad confiables.
- **Fase 3 — Visión en el borde:** cámara PoE + detección de persona/perro/paquete con el NPU Hailo, por zonas de la casa. Todo local.
- **Fase 4 — Hogar semántico:** una representación única y entendible de la casa ("modo, quién hay, el perro, la puerta, el estado de los sistemas") que consume el asistente.
- **Fase 5 — Hogar agéntico:** el salto. El asistente no ejecuta comandos: entiende el contexto y actúa (seguridad proactiva, confort, reportes).

> El norte: pasar de *"prendé la TV"* a *"¿qué pasa en casa?"* — y que la casa responda con sentido.

---

## 7. Paquetes (vendible)

| | **Essential** | **Plus** | **AI** |
|---|---|---|---|
| Nodo local privado | ✅ | ✅ | ✅ |
| Control unificado (TVs, luces, clima) | ✅ | ✅ | ✅ |
| Voz (Siri/Apple Home) + App | ✅ | ✅ | ✅ |
| Modos de casa + presencia por celular | ✅ | ✅ | ✅ |
| Backups cifrados + monitoreo | ✅ | ✅ | ✅ |
| Sensores de presencia física (puerta, mmWave) | — | ✅ | ✅ |
| Seguridad + simulación de presencia | — | ✅ | ✅ |
| Cámara + visión en el borde (persona/perro) | — | — | ✅ |
| Control por agente de IA (Claude/ChatGPT) | — | opcional | ✅ |
| Estado semántico del hogar | — | — | ✅ |

*(Nombres y alcance de paquetes ajustables según el segmento objetivo.)*

---

## 8. Modelo de negocio

Dos fuentes de ingreso, estándar en el rubro premium:

1. **Instalación (one-time):** hardware (el nodo + sensores/cámara según paquete) + puesta en marcha + onboarding de la casa. Margen sobre hardware + mano de obra.
2. **Suscripción (recurrente):** soporte, actualizaciones, monitoreo remoto de salud del sistema, backups gestionados y acceso remoto seguro. Es el ingreso recurrente que hace el negocio escalable.

*Ventaja de costos:* un solo nodo de bajo consumo corre todo; no hay costo de nube por casa (la IA es local), así que el margen de la suscripción es alto.

---

## 9. Mercado objetivo

- **Residencial premium** — casas y departamentos de alto valor donde la privacidad y la confiabilidad importan y hay poder adquisitivo.
- **Segunda vivienda / countries** — donde el acceso remoto, la seguridad y la simulación de presencia son muy valorados.
- **Clientes sensibles a la privacidad** — profesionales, directivos, perfiles públicos que no quieren micrófonos de Amazon/Google en casa.

---

## 10. Próximos pasos

1. Definir el **segmento inicial** y ajustar paquetes/precios.
2. Preparar una **demo en vivo** (casa piloto actual) — el producto ya existe, se puede mostrar hoy.
3. Cerrar la **Fase 2** (presencia física) para tener la primera venta con el diferencial completo.
4. Armar el **kit de instalación estándar** (BOM + proceso de onboarding) para replicar por casa.

---

*Todo lo descrito como "hecho" está en producción y es demostrable. El roadmap es ejecutable sobre la misma arquitectura — no requiere rehacer nada.*
