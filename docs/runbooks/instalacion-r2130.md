# Runbook: R2130 — instalación y recovery

## Acceso
- `ssh r2130` desde el mini-PC (alias en ~/.ssh/config → `pi@192.168.1.17`, clave `~/.ssh/minipc-to-raspi5`).
- Servicios: HA en http://192.168.1.17:8123, MQTT en 192.168.1.17:1883.
- Deploy key de GitHub: solo lectura (`r2130-deploy-readonly`). Los commits salen del mini-PC; la R2130 solo hace `git pull`.

## Recovery desde cero
1. Flashear Raspberry Pi OS Lite 64-bit al NVMe (usuario `pi`, SSH por clave,
   hostname `r2130`, TZ America/Argentina/Buenos_Aires).
2. `curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker pi`
3. Generar clave `ssh-keygen -t ed25519` y re-autorizarla como deploy key (read-only) del repo.
4. `sudo mkdir -p /opt/home-automation && sudo chown pi: /opt/home-automation`
   `git clone git@github.com:Ltaverna/home-automation.git /opt/home-automation`
5. Restaurar del último backup (tiene .env, mosquitto/config/passwd y
   homeassistant/.storage): `sudo tar -xzf config-<fecha>.tar.gz -C /opt`
   (o recrear .env desde .env.example + passwd con mosquitto_passwd si no hay backup).
6. Permisos mosquitto: `sudo chown 1883:1883 mosquitto/config/passwd mosquitto/data mosquitto/log && sudo chmod 600 mosquitto/config/passwd`
7. `cd /opt/home-automation && docker compose up -d`
8. Re-agregar el cron de backup: `30 4 * * * /opt/home-automation/scripts/backup.sh`

## Backups
- Nocturno 04:30 (cron de root) → /opt/backups/home-automation/ (14 días de retención).
- Las configs también están en git; .env / homeassistant/.storage / mosquitto passwd SOLO en el backup.

## Notas del hardware
- reComputer AI R2130: Pi 5 8GB + Hailo-8 26 TOPS (`/dev/hailo0`, driver de fábrica) + NVMe 512GB.
- Para Fase 4 (Frigate 0.16): verificar HailoRT == 4.21.0 en el host; si no coincide,
  usar el script oficial `user_installation.sh` de Frigate, NO el paquete apt.
