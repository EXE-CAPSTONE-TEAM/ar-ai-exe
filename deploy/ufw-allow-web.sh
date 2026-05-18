#!/usr/bin/env bash
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo SSH_PORT=${SSH_PORT} bash deploy/ufw-allow-web.sh" >&2
  exit 1
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment "SSH"
ufw allow 80/tcp comment "HTTP for Caddy ACME redirect"
ufw allow 443/tcp comment "HTTPS public web"
ufw --force enable
ufw status verbose