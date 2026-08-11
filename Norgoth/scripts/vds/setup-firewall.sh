#!/usr/bin/env bash
# Restrict public ingress to SSH + HTTP/HTTPS.
#
# IMPORTANT: this host uses a non-default SSH port. Allow it BEFORE enabling
# UFW, or you will lock yourself out of the VDS.
#
# Override with: SSH_PORT=35342 ./setup-firewall.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

SSH_PORT="${SSH_PORT:-35342}"

if ! [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || (( SSH_PORT < 1 || SSH_PORT > 65535 )); then
  echo "Invalid SSH_PORT=${SSH_PORT}" >&2
  exit 1
fi

# Allow SSH on the real listen port first (do not rely on the OpenSSH app profile;
# that typically only opens 22/tcp).
ufw allow "${SSH_PORT}/tcp" comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

ufw default deny incoming
ufw default allow outgoing
ufw --force enable
ufw status verbose

echo "Firewall configured: ${SSH_PORT}/tcp (SSH), 80/tcp, 443/tcp."
echo "Verify SSH still works before closing this session:"
echo "  ssh -p ${SSH_PORT} root@<host>"
