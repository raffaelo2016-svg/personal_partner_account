#!/usr/bin/env bash
set -uo pipefail

APP_DIR=/srv/personal_partner_account
STATE_DIR=/var/lib/kobinetur-health
LOG=/var/log/kobinetur-health.log
FAIL_FILE="$STATE_DIR/fail_count"
RESTART_THRESHOLD=3
COMPOSE="docker compose -f docker-compose.prod.yml"

mkdir -p "$STATE_DIR"
touch "$LOG"

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
prev_fails=$(cat "$FAIL_FILE" 2>/dev/null || echo 0)

if curl -fsS --max-time 10 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  if [ "$prev_fails" -gt 0 ]; then
    echo "$(now) RECOVERED after $prev_fails fails" >> "$LOG"
  fi
  echo 0 > "$FAIL_FILE"
  exit 0
fi

fails=$((prev_fails + 1))
echo "$fails" > "$FAIL_FILE"
echo "$(now) FAIL #$fails /health not responding" >> "$LOG"

if [ "$fails" -ge "$RESTART_THRESHOLD" ]; then
  echo "$(now) ATTEMPT restart backend (fails=$fails)" >> "$LOG"
  cd "$APP_DIR" && $COMPOSE restart backend >> "$LOG" 2>&1 || true
  echo 0 > "$FAIL_FILE"
fi
