#!/usr/bin/env bash
# Идемпотентная установка on-server healthcheck monitoring.
# Запускать на сервере от root:   bash deploy/monitoring/install.sh
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

install -m 0755 "$SRC_DIR/healthcheck.sh" /usr/local/bin/kobinetur-healthcheck.sh
install -m 0644 "$SRC_DIR/kobinetur-health.service" /etc/systemd/system/kobinetur-health.service
install -m 0644 "$SRC_DIR/kobinetur-health.timer"   /etc/systemd/system/kobinetur-health.timer

# Создаём logrotate-правило (держим 14 дней логов)
cat > /etc/logrotate.d/kobinetur-health <<'LOGROTATE'
/var/log/kobinetur-health.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE

systemctl daemon-reload
systemctl enable --now kobinetur-health.timer

echo "Installed. Status:"
systemctl list-timers kobinetur-health.timer --no-pager || true
echo "Logs: tail -f /var/log/kobinetur-health.log"
