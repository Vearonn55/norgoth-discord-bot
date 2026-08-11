#!/usr/bin/env bash
# Restrict public ingress to SSH + HTTP/HTTPS.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
echo "Firewall configured: 22/80/443 only."
