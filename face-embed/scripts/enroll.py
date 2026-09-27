#!/usr/bin/env python3
"""Enrolar una cara desde la cámara USB en la FaceEmbed API.
Uso (en la R2130): python3 enroll.py <user_id> [n_tomas]
Captura n tomas (default 5) de /dev/video0 y las agrega a la colección 'depto'.
Poné al sujeto de frente, buena luz, ~1 m, variando levemente la pose entre tomas.
"""
import base64, json, urllib.request, subprocess, time, sys

API = "http://localhost:8000"
COLL = "depto"
user = sys.argv[1] if len(sys.argv) > 1 else "lucas"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def post(path, obj):
    req = urllib.request.Request(API + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


ok = 0
for i in range(n):
    subprocess.run(["fswebcam", "-d", "/dev/video0", "-r", "1280x720",
                    "--no-banner", "-q", "/tmp/cap.jpg"], check=True)
    img = base64.b64encode(open("/tmp/cap.jpg", "rb").read()).decode()
    faces = post("/detect_and_embed", {"image_base64": img, "confidence_threshold": 0.5})
    if faces:
        faces.sort(key=lambda f: f.get("detection_confidence", 0), reverse=True)
        post("/vectors/add", {"collection": COLL, "user_id": user,
                              "vector": faces[0]["embedding"]["vector"]})
        ok += 1
        print("toma", i + 1, "enrolada (conf %.2f)" % faces[0]["detection_confidence"])
    else:
        print("toma", i + 1, "sin cara, salteada")
    time.sleep(2.5)
print("total enroladas para %s: %d" % (user, ok))
