#!/usr/bin/env python3
"""Loop de reconocimiento facial → MQTT para Home Assistant.
Captura /dev/video0 cada INTERVAL s, consulta al face-embed, y publica a MQTT
el último reconocido (lucas / desconocido / nadie) con MQTT Discovery.
"""
import base64, json, os, subprocess, time, datetime
import requests
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "ha")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
FACE_EMBED_URL = os.environ.get("FACE_EMBED_URL", "http://face-embed:8000")
COLLECTION = os.environ.get("COLLECTION", "depto")
THRESHOLD = float(os.environ.get("THRESHOLD", "0.45"))
INTERVAL = float(os.environ.get("INTERVAL", "4"))
VIDEO_DEV = os.environ.get("VIDEO_DEV", "/dev/video0")

STATE_TOPIC = "depto/face/state"
ATTRS_TOPIC = "depto/face/attrs"
DISCOVERY_TOPIC = "homeassistant/sensor/face_ultima_cara/config"
DISCOVERY_PAYLOAD = {
    "name": "Última cara",
    "unique_id": "face_ultima_cara",
    "state_topic": STATE_TOPIC,
    "json_attributes_topic": ATTRS_TOPIC,
    "icon": "mdi:face-recognition",
}


def capture_jpg(path="/tmp/f.jpg"):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "v4l2", "-i", VIDEO_DEV,
         "-frames:v", "1", "-q:v", "3", path],
        check=True, timeout=15,
    )
    return path


def recognize():
    """Devuelve (estado, similarity). estado: user_id | 'desconocido' | 'nadie'."""
    path = capture_jpg()
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    faces = requests.post(f"{FACE_EMBED_URL}/detect_and_embed",
                          json={"image_base64": img, "confidence_threshold": 0.5},
                          timeout=20).json()
    if not faces:
        return "nadie", None
    faces.sort(key=lambda x: x.get("detection_confidence", 0), reverse=True)
    vec = faces[0]["embedding"]["vector"]
    res = requests.post(f"{FACE_EMBED_URL}/vectors/search",
                        json={"collection": COLLECTION, "vector": vec, "threshold": THRESHOLD},
                        timeout=20).json()
    results = res.get("results") or []
    if res.get("status") == "found" and results:
        return results[0]["user_id"], round(float(results[0]["similarity"]), 3)
    return "desconocido", None


def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    client.publish(DISCOVERY_TOPIC, json.dumps(DISCOVERY_PAYLOAD), qos=1, retain=True)
    print("face-recognizer iniciado", flush=True)
    while True:
        try:
            estado, sim = recognize()
            attrs = {"similarity": sim, "visto": datetime.datetime.now().isoformat(timespec="seconds")}
            client.publish(STATE_TOPIC, estado, qos=0, retain=True)
            client.publish(ATTRS_TOPIC, json.dumps(attrs), qos=0, retain=True)
            print("estado:", estado, "sim:", sim, flush=True)
        except Exception as e:
            print("error en ciclo:", repr(e), flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
