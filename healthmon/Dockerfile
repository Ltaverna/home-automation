FROM python:3.11-slim

RUN pip install --no-cache-dir requests==2.31.0 paho-mqtt==1.6.1

COPY monitor.py /app/monitor.py
WORKDIR /app
CMD ["python3", "-u", "monitor.py"]
