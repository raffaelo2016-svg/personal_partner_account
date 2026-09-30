#!/usr/bin/env bash
set -euo pipefail

COMPOSE=${COMPOSE:-"docker compose -f docker-compose.prod.yml"}

fail=0

echo "[security] Check protected Docker port mappings"
for spec in db:5432 redis:6379 minio:9000 minio:9001; do
  service="${spec%:*}"
  port="${spec#*:}"
  mappings="$($COMPOSE port "$service" "$port" 2>/dev/null || true)"
  require_loopback=0
  valid_loopback=0
  if [ "$spec" = "minio:9000" ]; then
    require_loopback=1
  fi

  if [ -z "$mappings" ]; then
    if [ "$require_loopback" = 1 ]; then
      echo "  FAIL: minio:9000 is not published on loopback; file downloads would return 502" >&2
      fail=1
    else
      echo "  OK: $service:$port is not published"
    fi
    continue
  fi

  while IFS= read -r mapping; do
    [ -z "$mapping" ] && continue
    case "$mapping" in
      *:0 | *]:0)
        if [ "$require_loopback" = 1 ]; then
          echo "  FAIL: minio:9000 has no usable loopback mapping" >&2
          fail=1
        else
          echo "  OK: $service:$port is not published"
        fi
        ;;
      127.0.0.1:* | \[::1\]:*)
        echo "  OK: $service:$port -> $mapping"
        valid_loopback=1
        ;;
      *)
        echo "  FAIL: $service:$port is published on $mapping" >&2
        fail=1
        ;;
    esac
  done <<< "$mappings"

  if [ "$require_loopback" = 1 ] && [ "$valid_loopback" != 1 ]; then
    echo "  FAIL: minio:9000 has no valid loopback mapping" >&2
    fail=1
  fi
done

if command -v ss >/dev/null 2>&1; then
  echo "[security] Check host listeners"
  listeners="$(ss -H -ltn | awk '{print $4}' || true)"
  for port in 5432 6379 9000 9001; do
    matches="$(printf '%s\n' "$listeners" | awk -v port=":$port" 'index($0, port) == length($0) - length(port) + 1')"
    if [ -z "$matches" ]; then
      echo "  OK: no host listener on :$port"
      continue
    fi

    while IFS= read -r listener; do
      [ -z "$listener" ] && continue
      case "$listener" in
        127.0.0.1:* | \[::1\]:*)
          echo "  OK: :$port listens on loopback ($listener)"
          ;;
        *)
          echo "  FAIL: :$port listens on non-loopback address ($listener)" >&2
          fail=1
          ;;
      esac
    done <<< "$matches"
  done
else
  echo "[security] ss not found; skipped host listener check"
fi

if [ "$fail" != 0 ]; then
  echo "[security] Protected services must not be exposed publicly." >&2
  exit 1
fi

echo "[security] OK"
