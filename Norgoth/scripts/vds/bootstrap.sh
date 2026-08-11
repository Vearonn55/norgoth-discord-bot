#!/usr/bin/env bash
# Bootstrap a Ubuntu VDS for NorBot (run as root once).
set -euo pipefail

NORBOT_USER="${NORBOT_USER:-norbot}"
OPT_ROOT="${OPT_ROOT:-/opt/norbot}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

echo "Creating user ${NORBOT_USER}…"
if ! id "${NORBOT_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${NORBOT_USER}"
fi

echo "Installing Docker (Ubuntu)…"
apt-get update
apt-get install -y ca-certificates curl gnupg ufw nginx
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
. /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker "${NORBOT_USER}"

echo "Creating ${OPT_ROOT} layout…"
mkdir -p \
  "${OPT_ROOT}/deploy" \
  "${OPT_ROOT}/env" \
  "${OPT_ROOT}/scripts" \
  "${OPT_ROOT}/releases" \
  "${OPT_ROOT}/backups/postgres" \
  /var/www/certbot
chown -R "${NORBOT_USER}:${NORBOT_USER}" "${OPT_ROOT}"
chmod 750 "${OPT_ROOT}"
chmod 700 "${OPT_ROOT}/env"

echo "Bootstrap complete. Next:"
echo "  1) Copy deploy manifests into ${OPT_ROOT}/deploy"
echo "  2) Create ${OPT_ROOT}/env/production.env and test.env (mode 600)"
echo "  3) Run scripts/vds/setup-firewall.sh"
echo "  4) Install Nginx configs + Certbot"
echo "  5) Configure GitHub Deploy Key + Actions SSH key for ${NORBOT_USER}"
