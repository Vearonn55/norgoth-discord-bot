#!/usr/bin/env bash
# Install the loopback HTTPS deploy agent (run as root from a laptop SSH session).
#
# GitHub-hosted runners often cannot reach the VDS SSH port (cloud firewall /
# fail2ban / Cloudflare hostname). Port 443 is already public; this agent lets
# Actions apply a GHCR tag without inbound SSH.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
AGENT_SRC="${SCRIPT_DIR}/ci-apply-agent.py"
UNIT_SRC="${SCRIPT_DIR}/norbot-ci-apply.service"
APPLY_SRC="${SCRIPT_DIR}/../docker/apply-release.sh"
if [[ ! -f "${APPLY_SRC}" ]]; then
  APPLY_SRC="${REPO_ROOT}/Norgoth/scripts/docker/apply-release.sh"
fi

if [[ ! -f "${AGENT_SRC}" || ! -f "${APPLY_SRC}" ]]; then
  echo "Could not find ci-apply sources. Run this from a git checkout of the repo." >&2
  echo "Looked for ${AGENT_SRC}" >&2
  exit 1
fi

NORBOT_USER="${NORBOT_USER:-norbot}"
OPT_ROOT="${OPT_ROOT:-/opt/norbot}"
install -d -m 0750 -o "${NORBOT_USER}" -g "${NORBOT_USER}" \
  "${OPT_ROOT}/ci-apply" "${OPT_ROOT}/scripts" "${OPT_ROOT}/env"

install -m 0755 -o "${NORBOT_USER}" -g "${NORBOT_USER}" \
  "${AGENT_SRC}" "${OPT_ROOT}/ci-apply/ci-apply-agent.py"
DOCKER_SCRIPTS="$(cd "${SCRIPT_DIR}/../docker" && pwd)"
if [[ -d "${DOCKER_SCRIPTS}" ]]; then
  for src in "${DOCKER_SCRIPTS}"/*.sh; do
    install -m 0755 -o "${NORBOT_USER}" -g "${NORBOT_USER}" \
      "${src}" "${OPT_ROOT}/scripts/$(basename "${src}")"
  done
else
  install -m 0755 -o "${NORBOT_USER}" -g "${NORBOT_USER}" \
    "${APPLY_SRC}" "${OPT_ROOT}/scripts/apply-release.sh"
fi

SECRET_FILE="${OPT_ROOT}/env/ci-apply.secret"
if [[ ! -s "${SECRET_FILE}" ]]; then
  umask 077
  openssl rand -hex 32 > "${SECRET_FILE}"
fi
chown "${NORBOT_USER}:${NORBOT_USER}" "${SECRET_FILE}"
chmod 600 "${SECRET_FILE}"

install -m 0644 "${UNIT_SRC}" /etc/systemd/system/norbot-ci-apply.service
systemctl daemon-reload
systemctl enable --now norbot-ci-apply.service
systemctl --no-pager --full status norbot-ci-apply.service || true

SNIPPET=/etc/nginx/snippets/norbot-ci-apply.inc
cat > "${SNIPPET}" <<'EOF'
location = /__norbot/ci-apply {
    limit_req zone=norbot_ci burst=2 nodelay;
    proxy_pass http://127.0.0.1:9277/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 900s;
    proxy_send_timeout 60s;
    client_max_body_size 16k;
}
EOF

python3 - <<'PY'
from pathlib import Path
import re

zone_line = "limit_req_zone $binary_remote_addr zone=norbot_ci:10m rate=2r/m;"
include_line = "    include snippets/norbot-ci-apply.inc;"
candidates = [
    Path("/etc/nginx/sites-available/norbot.conf"),
    Path("/etc/nginx/sites-enabled/norbot.conf"),
    Path("/etc/nginx/sites-available/norbot-test.conf"),
    Path("/etc/nginx/sites-enabled/norbot-test.conf"),
]
seen = set()
for path in candidates:
    if not path.is_file():
        continue
    resolved = path.resolve()
    if resolved in seen:
        continue
    seen.add(resolved)
    text = path.read_text(encoding="utf-8")
    original = text
    if "zone=norbot_ci" not in text:
        idx = text.rfind("limit_req_zone")
        if idx != -1:
            nl = text.find("\n", idx)
            text = text[: nl + 1] + zone_line + "\n" + text[nl + 1 :]
        else:
            text = zone_line + "\n" + text
    if "__norbot/ci-apply" not in text:
        updated, n = re.subn(
            r"(location \^~ /internal/ \{.*?\n    \}\n)",
            r"\1\n" + include_line + "\n",
            text,
            count=0,
            flags=re.S,
        )
        if n:
            text = updated
        else:
            print(f"Add this inside the api.* server block in {path}:")
            print(include_line)
    if text != original:
        bak = path.with_name(path.name + ".bak-ci-apply")
        if not bak.exists():
            bak.write_text(original, encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"Updated {path}")
PY

if nginx -t; then
  systemctl reload nginx
  echo "nginx reloaded with /__norbot/ci-apply."
else
  echo "nginx -t failed; restoring site conf backups if present." >&2
  for bak in /etc/nginx/sites-available/*.bak-ci-apply /etc/nginx/sites-enabled/*.bak-ci-apply; do
    [[ -f "${bak}" ]] || continue
    orig="${bak%.bak-ci-apply}"
    cp -a "${bak}" "${orig}"
  done
  nginx -t || true
  echo "Add snippets/norbot-ci-apply.inc inside the api.* server block manually." >&2
fi
echo
echo "Put this value in GitHub Environments test + production as DEPLOY_APPLY_SECRET:"
echo
cat "${SECRET_FILE}"
echo
echo "Optional: DEPLOY_APPLY_URL (defaults to https://api.norbot.io/__norbot/ci-apply"
echo "or https://api.test.norbot.io/__norbot/ci-apply)."
echo
echo "To apply the images GitHub already pushed, from this host:"
echo "  sudo -u ${NORBOT_USER} -H env NORBOT_IMAGE_OWNER=vearonn55 \\"
echo "    ${OPT_ROOT}/scripts/apply-release.sh production <40-char-sha>"
