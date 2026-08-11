#!/usr/bin/env bash
# Install Certbot and obtain certificates for NorBot hostnames.
# Requires DNS A records pointing at this VDS first.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

EMAIL="${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL}"
DOMAIN_MODE="${1:-production}"

apt-get update
apt-get install -y certbot python3-certbot-nginx

case "${DOMAIN_MODE}" in
  production)
    certbot --nginx \
      -m "${EMAIL}" --agree-tos --no-eff-email --redirect \
      -d norbot.io -d www.norbot.io -d api.norbot.io
    ;;
  test)
    certbot --nginx \
      -m "${EMAIL}" --agree-tos --no-eff-email --redirect \
      -d test.norbot.io -d api.test.norbot.io
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

systemctl enable --now certbot.timer || true
echo "TLS certificates installed for ${DOMAIN_MODE}."
