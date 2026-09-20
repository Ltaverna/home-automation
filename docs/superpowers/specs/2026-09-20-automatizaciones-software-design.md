# Spec: Automatizaciones de software puro (sin hardware nuevo)

**Fecha:** 2026-09-20
**Estado:** aprobado
**Contexto:** Extiende la Fase 1.5 con automatizaciones que usan solo lo ya integrado
(TVs, `person.lucas`, `input_select.house_mode`, notificaciones). Sin compras.

## Objetivo

Cuatro automatizaciones que hacen que la casa "haga cosas sola" con el hardware actual,
como puente hasta que llegue la compra USA (Fase 2 = presencia real con sensores).

## Helpers nuevos (`configuration.yaml`)

```yaml
input_boolean:
  modo_paseo:
    name: Modo paseo
    icon: mdi:dog-side
  modo_simulacion:
    name: Modo simulación (anti-robo)
    icon: mdi:shield-home

timer:
  paseo:
    name: Paseo perro
    duration: "00:30:00"
    restore: true
```

Ambos `input_boolean` se agregan al filtro del HomeKit Bridge (puerto 21063) → Siri:
"activá modo paseo", "activá modo simulación".

## 1. Despertar suave

- **Trigger:** `time` a las `08:30:00`.
- **Condiciones:** día laborable (`mon`–`fri`) **y** `person.lucas` = `home`.
- **Acción:** `script.flow_canal_dormitorio` con `canal: 14` (ya encadena WoL → abrir Flow →
  dígitos 1,4 → ENTER).
- **Nota:** si `person.lucas` no está `home` (viaje), no se dispara.

## 2. Modo pasear al perro

- **`script.iniciar_paseo`:** `input_boolean.turn_on modo_paseo` + apagar ambas TVs +
  `timer.start paseo` (30 min) + notificación "🐕 Paseo — AWAY suspendido 30 min".
- **`automation.modo_paseo_fin`:** trigger = `timer.finished` (event `timer.paseo`) **o**
  `person.lucas` → `home`. Acción: `timer.cancel paseo` + `input_boolean.turn_off modo_paseo`.
- **Modificación a `house_mode_salida`:** agregar condición `not is_state('input_boolean.modo_paseo','on')`
  para que salir a pasear no dispare AWAY ni apague/notifique.
- `script.iniciar_paseo` se expone para Siri/dashboard (o se usa el switch `input_boolean.modo_paseo`
  directo, que al encenderse dispara el script vía una automatización `modo_paseo_inicio`).

**Decisión de disparo:** el encendido de `input_boolean.modo_paseo` (desde Siri/HomeKit o
dashboard) es el trigger. Una automatización `modo_paseo_inicio` (trigger: modo_paseo → on)
ejecuta las acciones de inicio. Así el mismo switch sirve para Siri y para el dashboard, sin
depender de llamar un script por separado.

## 3. Aviso TV prendida + AWAY

- **Trigger:** `media_player.lg_webos_tv_oled55c3psa` **o** `media_player.tv_dormitorio`
  pasa a `on`, sostenido `for: 00:02:00`.
- **Condiciones:** `input_select.house_mode` = `AWAY` **y** `not modo_simulacion`.
- **Acción:** notificación accionable a `notify.mobile_app_lucass_iphone`:
  - título "📺 TV encendida sin nadie en casa"
  - `data.actions`: un botón con `action: APAGAR_TVS`, título "Apagar".
- **`automation.aviso_tv_apagar`:** trigger = event `mobile_app_notification_action` con
  `action == APAGAR_TVS`. Acción: `media_player.turn_off` ambas TVs.

## 4. Presencia simulada (anti-robo)

- **`automation.simulacion_toggle`:**
  - Trigger: `time_pattern` cada 30 min (`minutes: "/30"`).
  - Condiciones: `modo_simulacion` = on, `house_mode` = AWAY, hora entre `19:00` y `23:30`.
  - Acción: 50% de probabilidad (`{{ range(0,2)|random == 1 }}`) de `media_player.toggle`
    sobre el LG del living. Patrón irregular = parece ocupado.
- **`automation.simulacion_fin`:** trigger `time` `23:30:00`; condición `modo_simulacion` on;
  acción: apagar el LG (nadie deja la TV toda la noche).

## Interdependencias (ya contempladas)

| Automatización existente/nueva | Ajuste |
|---|---|
| `house_mode_salida` | + condición `not modo_paseo` |
| `aviso_tv_away` (nueva) | + condición `not modo_simulacion` |
| `simulacion_toggle` (nueva) | enciende el LG estando AWAY; el aviso no dispara gracias a la condición de arriba |

## Archivos a tocar

- `homeassistant/configuration.yaml` — `input_boolean`, `timer`, filtro HomeKit.
- `homeassistant/automations.yaml` — 6 automatizaciones nuevas + 1 condición a `house_mode_salida`.
- `homeassistant/scripts.yaml` — `iniciar_paseo` (acciones de inicio del paseo).

## Criterios de éxito

- 08:30 de un día laborable estando en casa → TV dormitorio en Flow canal 14.
- Activar modo paseo → TVs off, sin notif de AWAY; a los 30 min (o al volver) se desactiva solo.
- Estando AWAY con una TV encendida 2 min → llega notif con botón Apagar que funciona.
- Con modo simulación on y AWAY, entre 19 y 23:30 la TV del living se prende/apaga sola de
  forma irregular; a las 23:30 queda apagada; el aviso de TV no molesta.

## Fuera de alcance / futuro

- **Reporte diario** (resumen de ocupación/uso): pendiente, baja prioridad.
- **Servidor MCP de Home Assistant** para controlar la casa desde Claude/ChatGPT: HA ya trae la
  integración oficial "Model Context Protocol Server" (expone Assist a clientes MCP). Proyecto
  aparte — no requiere construir un MCP de cero, solo activarlo y conectar el cliente.
