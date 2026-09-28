#!/usr/bin/env python3
"""Monitor de salud → MQTT + watchdog externo (dead-man switch).
Chequea servicios por HTTP cada INTERVAL s, publica binary_sensor por MQTT Discovery,
y si HA está OK pinguea healthchecks.io. Si HA/Raspi/internet caen, deja de pingar.
"""
import json, os, time, datetime
import requests
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "ha")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
HEALTHCHECKS_URL = os.environ.get("HEALTHCHECKS_URL", "")
INTERVAL = float(os.environ.get("INTERVAL", "60"))

NODE = os.environ.get("NODE_IP", "192.168.1.17")


def check_http(url, ok_codes=(200, 302), needs=None):
    try:
        r = requests.get(url, timeout=8)
        if r.status_code not in ok_codes:
            return False, f"HTTP {r.status_code}"
        if needs and needs not in r.text:
            return False, "respuesta inesperada"
        return True, "ok"
    except Exception as e:
        return False, repr(e)[:80]


def check_faceembed():
    return check_http("http://face-embed:8000/health", needs='"status"')


def check_mcp():
    # El server ha_mcp_tools responde 404 en "/" (el MCP vive en /<secret_path>);
    # eso es transporte vivo. Solo 5xx / timeout / conexión caída = DOWN.
    try:
        r = requests.get(f"http://{NODE}:9584/", timeout=8)
        if r.status_code >= 500:
            return False, f"HTTP {r.status_code}"
        return True, f"HTTP {r.status_code}"
    except Exception as e:
        return False, repr(e)[:80]


def check_ha():
    return check_http(f"http://{NODE}:8123/", ok_codes=(200, 302))


SERVICES = {
    "faceembed": ("Salud face-embed", check_faceembed),
    "mcp": ("Salud MCP", check_mcp),
    "ha": ("Salud Home Assistant", check_ha),
}


def discovery_payload(key, name):
    return {
        "name": name,
        "unique_id": f"salud_{key}",
        "state_topic": f"depto/salud/{key}",
        "json_attributes_topic": f"depto/salud/{key}/attrs",
        "device_class": "problem",
        "payload_on": "ON",
        "payload_off": "OFF",
    }


def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    for key, (name, _) in SERVICES.items():
        topic = f"homeassistant/binary_sensor/salud_{key}/config"
        client.publish(topic, json.dumps(discovery_payload(key, name)), qos=1, retain=True)
    print("healthmon iniciado", flush=True)
    while True:
        ha_ok = False
        for key, (name, fn) in SERVICES.items():
            try:
                ok, detail = fn()
            except Exception as e:
                ok, detail = False, repr(e)[:80]
            if key == "ha":
                ha_ok = ok
            state = "OFF" if ok else "ON"
            attrs = {"checked": datetime.datetime.now().isoformat(timespec="seconds"), "detail": detail}
            client.publish(f"depto/salud/{key}", state, qos=0, retain=True)
            client.publish(f"depto/salud/{key}/attrs", json.dumps(attrs), qos=0, retain=True)
            print(f"{key}: {'ok' if ok else 'FAIL'} ({detail})", flush=True)
        if ha_ok and HEALTHCHECKS_URL:
            try:
                requests.get(HEALTHCHECKS_URL, timeout=8)
            except Exception as e:
                print("ping healthchecks falló:", repr(e)[:80], flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
