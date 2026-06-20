#!/usr/bin/env bash
set -euo pipefail

PROTECTED_PORTS=5432,6379,9000,9001

add_rule() {
  local bin="$1"
  local chain="$2"
  shift 2

  if ! command -v "$bin" >/dev/null 2>&1; then
    return
  fi

  if "$bin" -w -C "$chain" "$@" 2>/dev/null; then
    return
  fi

  "$bin" -w -I "$chain" "$@"
}

ensure_docker_user_chain() {
  if ! command -v iptables >/dev/null 2>&1; then
    return
  fi

  iptables -w -N DOCKER-USER 2>/dev/null || true
  iptables -w -C FORWARD -j DOCKER-USER 2>/dev/null || \
    iptables -w -I FORWARD -j DOCKER-USER
}

echo "[firewall] Block protected service ports from external networks"

ensure_docker_user_chain

# Docker-published ports pass through FORWARD/DOCKER-USER. Host listeners use INPUT.
add_rule iptables DOCKER-USER ! -i lo -p tcp -m multiport --dports "$PROTECTED_PORTS" -j DROP
add_rule iptables INPUT       ! -i lo -p tcp -m multiport --dports "$PROTECTED_PORTS" -j DROP

if command -v ip6tables >/dev/null 2>&1; then
  ip6tables -w -N DOCKER-USER 2>/dev/null || true
  ip6tables -w -C FORWARD -j DOCKER-USER 2>/dev/null || \
    ip6tables -w -I FORWARD -j DOCKER-USER 2>/dev/null || true
  add_rule ip6tables DOCKER-USER ! -i lo -p tcp -m multiport --dports "$PROTECTED_PORTS" -j DROP
  add_rule ip6tables INPUT       ! -i lo -p tcp -m multiport --dports "$PROTECTED_PORTS" -j DROP
fi

echo "[firewall] OK"
