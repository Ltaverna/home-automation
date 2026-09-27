#!/usr/bin/env python3
"""Reconocer caras desde la cámara USB contra la colección 'depto'.
Uso (en la R2130): python3 recognize.py
Threshold 0.45: un enrolado bien capturado da ~0.8; desconocidos quedan por debajo.
"""
import base64, json, urllib.request, subprocess

API = "http://localhost:8000"
COLL = "depto"
THRESHOLD = 0.45

subprocess.run(["fswebcam", "-d", "/dev/video0", "-r", "1280x720",
                "--no-banner", "-q", "/tmp/cap.jpg"], check=True)
img = base64.b64encode(open("/tmp/cap.jpg", "rb").read()).decode()


def post(path, obj):
    req = urllib.request.Request(API + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


faces = post("/detect_and_embed", {"image_base64": img, "confidence_threshold": 0.5})
print("caras detectadas:", len(faces))
for i, f in enumerate(faces):
    res = post("/vectors/search", {"collection": COLL,
                                   "vector": f["embedding"]["vector"], "threshold": THRESHOLD})
    print("  cara", i, "->", json.dumps(res))
