#!/usr/bin/env bash
# Métricas del host R2130 → MQTT Discovery (sensores en HA). Corre por cron como root.
# Nota: la temperatura del Hailo-8 no se expone (ni hailortcli on-demand ni hwmon/sysfs);
# en su lugar se publica la temperatura del NVMe (hwmon). El resto: CPU, RAM, temp CPU, disco, SMART.
set -uo pipefail

# cron trae un PATH mínimo (/usr/bin:/bin); smartctl vive en /usr/sbin y docker en /usr/bin.
export PATH=/usr/sbin:/usr/bin:/sbin:/bin:$PATH

ENV_FILE=/opt/home-automation/.env
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
MQTT_USER="${MQTT_USER:-ha}"; MQTT_PASSWORD="${MQTT_PASSWORD:-}"

pub() {  # pub <topic> <payload> [retain]
  local topic="$1" payload="$2" retain="${3:-}"
  docker exec mosquitto mosquitto_pub -u "$MQTT_USER" -P "$MQTT_PASSWORD" \
    -t "$topic" -m "$payload" ${retain:+-r} 2>/dev/null || true
}

discovery() {  # discovery <key> <name> <device_class|""> <unit|""> [binary_sensor]
  local key="$1" name="$2" dclass="$3" unit="$4" kind="${5:-sensor}"
  local cfg="{\"name\":\"$name\",\"unique_id\":\"node_$key\",\"object_id\":\"node_$key\",\"state_topic\":\"depto/nodo/$key\","
  cfg+="\"device\":{\"identifiers\":[\"r2130_node\"],\"name\":\"Nodo R2130\"}"
  [ -n "$dclass" ] && cfg+=",\"device_class\":\"$dclass\""
  [ -n "$unit" ] && cfg+=",\"unit_of_measurement\":\"$unit\""
  [ "$kind" = "binary_sensor" ] && cfg+=",\"payload_on\":\"ON\",\"payload_off\":\"OFF\""
  cfg+="}"
  pub "homeassistant/$kind/node_$key/config" "$cfg" retain
}

# --- Discovery (retained) ---
discovery cpu "Nodo CPU" "" "%"
discovery ram "Nodo RAM" "" "%"
discovery temp_cpu "Nodo Temp CPU" temperature "°C"
discovery temp_nvme "Nodo Temp NVMe" temperature "°C"
discovery disk "Nodo Disco NVMe" "" "%"
discovery nvme_smart "Nodo SMART NVMe" problem "" binary_sensor
discovery last_backup_age "Nodo Antigüedad Backup" duration "h"

# --- CPU % (delta de /proc/stat en 1s) ---
read_cpu() { awk '/^cpu /{t=$2+$3+$4+$5+$6+$7+$8; i=$5; print t, i}' /proc/stat; }
r1=$(read_cpu); sleep 1; r2=$(read_cpu)
cpu=$(awk -v a="$r1" -v b="$r2" 'BEGIN{split(a,x," ");split(b,y," ");dt=y[1]-x[1];di=y[2]-x[2]; if(dt>0) printf "%.0f",(1-di/dt)*100; else print 0}')
pub depto/nodo/cpu "$cpu"

# --- RAM % ---
ram=$(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "%.0f",(1-a/t)*100}' /proc/meminfo)
pub depto/nodo/ram "$ram"

# --- Temp CPU (°C) ---
if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
  pub depto/nodo/temp_cpu "$(awk '{printf "%.1f",$1/1000}' /sys/class/thermal/thermal_zone0/temp)"
fi

# --- Temp NVMe (°C) — hwmon con name=nvme ---
for h in /sys/class/hwmon/hwmon*; do
  if [ "$(cat "$h/name" 2>/dev/null)" = "nvme" ] && [ -r "$h/temp1_input" ]; then
    pub depto/nodo/temp_nvme "$(awk '{printf "%.1f",$1/1000}' "$h/temp1_input")"
    break
  fi
done

# --- Disco / (%) ---
pub depto/nodo/disk "$(df -P / | tail -1 | awk '{gsub("%","",$5); print $5}')"

# --- SMART NVMe (PASSED → OFF / else ON) ---
if command -v smartctl >/dev/null; then
  if smartctl -H /dev/nvme0 2>/dev/null | grep -qi "PASSED"; then
    pub depto/nodo/nvme_smart "OFF"
  else
    pub depto/nodo/nvme_smart "ON"
  fi
fi

# --- Antigüedad del último backup off-site (horas) desde el marker local ---
MARKER=/opt/home-automation/.last-backup-offsite
if [ -f "$MARKER" ]; then
  now=$(date +%s); m=$(date -d "$(cat "$MARKER")" +%s 2>/dev/null || stat -c %Y "$MARKER")
  pub depto/nodo/last_backup_age "$(awk -v n="$now" -v m="$m" 'BEGIN{printf "%.1f",(n-m)/3600}')"
fi

echo "node-metrics OK: $(date -Is) cpu=${cpu} ram=${ram} disk=$(df -P / | tail -1 | awk '{print $5}')"
