FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests==2.31.0 paho-mqtt==1.6.1

COPY loop.py /app/loop.py
WORKDIR /app
CMD ["python3", "-u", "loop.py"]
