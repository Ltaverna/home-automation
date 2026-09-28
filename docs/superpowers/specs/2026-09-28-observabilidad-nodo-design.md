# Spec: Observabilidad de nodo (métricas del host R2130)

**Fecha:** 2026-09-28
**Estado:** aprobado
**Contexto:** Punto 3 (último) del hardening pre-Fase 2 (ver `docs/roadmap-evolucion-arquitectura.md`
§20-23). El `healthmon` mide salud de *servicios* (¿responden?); falta la salud del *nodo*
(CPU/RAM/temperatura/NVMe/Hailo), clave antes de sumar servicios pesados (Frigate, etc.).

## Objetivo

Publicar métricas de recursos del host R2130 como sensores en HA + alertas accionables, sin
infraestructura enterprise (nada de Prometheus/Grafana).

## Decisiones (del brainstorming)

- **Captura: script en el host → MQTT** (las métricas de temp/SMART/Hailo no son accesibles desde
  un contenedor sin privilegios). Coherente con el patrón de `healthmon` (MQTT Discovery).
- **Alcance: esenciales + alertas accionables** (no todas las del roadmap; evitar ruido).

## Componente `scripts/node-metrics.sh` (host, cron cada 1 min)

| Métrica | Fuente | Sensor HA | device_class / unidad |
|---|---|---|---|
| CPU % | `/proc/stat` (2 lecturas, delta 1s) | `sensor.node_cpu` | `%` |
| RAM % | `/proc/meminfo` (MemTotal, MemAvailable) | `sensor.node_ram` | `%` |
| Temp CPU | `/sys/class/thermal/thermal_zone0/temp` | `sensor.node_temp_cpu` | temperature, `°C` |
| Temp Hailo | `hailortcli` (subcomando de monitoreo) | `sensor.node_hailo_temp` | temperature, `°C` |
| Uso disco `/` | `df -P /` | `sensor.node_disk` | `%` |
| SMART NVMe | `smartctl -H /dev/nvme0` → PASSED/FAILED | `binary_sensor.node_nvme_smart` | problem |

- Publica a MQTT vía `docker exec mosquitto mosquitto_pub` (sin instalar clientes en el host),
  con `MQTT_USER`/`MQTT_PASSWORD` leídos del `.env`.
- **MQTT Discovery** (retained) al arrancar cada corrida: cada sensor con su config, agrupados en
  un device `Nodo R2130` (`device.identifiers: r2130_node`).
- Cada métrica en try/except: si una falla (ej. `hailortcli` no da temp), publica las demás igual.
- `set -uo pipefail`; log a stdout (cron → `/var/log/node-metrics.log`).

### Nota sobre la temp/util del Hailo
Se confirma el comando exacto en la implementación. Si `hailortcli` no expone temp/util de forma
simple y confiable, **se omite esa métrica** (el resto queda igual) y se documenta como pendiente.
No bloquea el resto de la observabilidad de nodo.

## Alertas — automatización en `packages/salud.yaml`

Nueva automatización `nodo_alerta` (junto a `salud_alerta`), solo accionables, con transición
(anti-spam):
- `sensor.node_disk` > 85 → "⚠️ Disco NVMe al {{ }}%"
- `sensor.node_temp_cpu` > 80 → "🌡️ CPU caliente ({{ }}°C)"
- `sensor.node_hailo_temp` > 80 (si existe el sensor) → "🌡️ Hailo caliente"
- `binary_sensor.node_nvme_smart` = on (problem) → "💾 SMART del NVMe: FALLA"

## Dashboard

Agregar a la vista "Salud" (`dashboards/remoto.yaml`) una tarjeta con `sensor.node_cpu`,
`node_ram`, `node_temp_cpu`, `node_hailo_temp`, `node_disk`, `binary_sensor.node_nvme_smart`.

## Cron

```
* * * * * /opt/home-automation/scripts/node-metrics.sh >> /var/log/node-metrics.log 2>&1
```
(root, para leer thermal/smartctl/hailo y usar docker).

## Dependencias / setup

- `smartmontools` en el host (`apt install smartmontools`) para `smartctl`.
- `hailortcli` ya instalado.
- Umbrales configurables como constantes en la automatización (85% disco, 80 °C).

## Verificación de éxito

- `sensor.node_cpu/node_ram/node_temp_cpu/node_disk` (+ `node_hailo_temp` si disponible) y
  `binary_sensor.node_nvme_smart` aparecen en HA con valores reales y se refrescan cada ~1 min.
- La vista "Salud" muestra las métricas del nodo.
- Forzar un umbral (ej. bajar temporalmente el umbral de disco) dispara la notif → confirma la alerta.
- `check_config` limpio.

## Documentación (MUST)

- `scripts/node-metrics.sh` autocomentado.
- `docs/estado-actual.md`: sensores de nodo + alertas.
- `docs/runbooks/pendientes.md`: marcar el punto 3 del hardening HECHO → **hardening completo**.
- `README.md`: mencionar observabilidad de nodo en servicios/roadmap.

## Fuera de alcance

- Métricas completas del roadmap §21 (swap, load, NVMe writes/temp, inference latency, docker
  per-container): se pueden sumar después si hacen falta; ahora solo las esenciales.
- Histórico/gráficas largas (HA ya guarda historia de los sensores; no se agrega Grafana).
- Auto-reparación (reiniciar servicios/throttle): solo alertar.
