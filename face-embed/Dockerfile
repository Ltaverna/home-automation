# FaceEmbed API (Seeed) dockerizada con HailoRT 4.20 — matchea el driver del host,
# sin tocar el sistema Hailo de Raspberry Pi OS.
# Los .deb 4.20 se copian al contexto (bajados con `apt-get download` en el host).
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip git ca-certificates \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# HailoRT 4.20 (userspace lib + binding Python) desde los .deb del repo de RPi OS.
# El driver del kernel (hailo_pci 4.20) lo provee el host vía /dev/hailo0.
COPY hailort_4.20.0-1_arm64.deb python3-hailort_4.20.0-1_arm64.deb /tmp/
RUN dpkg -i /tmp/hailort_4.20.0-1_arm64.deb /tmp/python3-hailort_4.20.0-1_arm64.deb \
    || apt-get update && apt-get install -f -y; rm -f /tmp/*.deb

# Código de la API + modelos (arcface_mobilefacenet.hef, scrfd_10g.hef vienen en el repo).
RUN git clone --depth 1 https://github.com/Seeed-Solution/face-recognition-api.git /app
WORKDIR /app

# Deps de la API SIN el hailort pip (usamos el python3-hailort del .deb, versión 4.20).
# opencv headless (sin GUI) para contenedor.
RUN pip install --break-system-packages --no-cache-dir \
    fastapi==0.104.1 "uvicorn[standard]==0.24.0.post1" pydantic==2.5.0 \
    numpy==1.26.2 opencv-python-headless==4.8.1.78 scikit-image==0.22.0 \
    requests==2.31.0 httpx==0.25.2

EXPOSE 8000
CMD ["bash", "-lc", "PYTHONPATH=src python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8000"]
