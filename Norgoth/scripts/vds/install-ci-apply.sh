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
  "${OPT_ROOT}/ci-apply" "${OPT_ROOT}/scripts" "${OPT_ROOT}/env" \
  "${OPT_ROOT}/releases" "${OPT_ROOT}/backups"

SRC_DIR="${OPT_ROOT}/src"
if [[ -d "${SRC_DIR}/.git" ]]; then
  chown -R "${NORBOT_USER}:${NORBOT_USER}" "${SRC_DIR}"
  sudo -u "${NORBOT_USER}" -H \
    git config --global --add safe.directory "${SRC_DIR}" 2>/dev/null || true
fi

for subdir in releases backups; do
  if [[ -d "${OPT_ROOT}/${subdir}" ]]; then
    chown -R "${NORBOT_USER}:${NORBOT_USER}" "${OPT_ROOT}/${subdir}"
  fi
done

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
import sys

zone_line = "limit_req_zone $binary_remote_addr zone=norbot_ci:10m rate=2r/m;"
include_line = "    include snippets/norbot-ci-apply.inc;"

candidates: list[Path] = []
for base in (Path("/etc/nginx/sites-available"), Path("/etc/nginx/sites-enabled")):
    if not base.is_dir():
        continue
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        name = path.name.lower()
        if "norbot" in name or name.endswith(".conf"):
            candidates.append(path)
# Also scan conf.d for api host configs not named norbot*.
conf_d = Path("/etc/nginx/conf.d")
if conf_d.is_dir():
    candidates.extend(sorted(p for p in conf_d.iterdir() if p.is_file()))

seen: set[Path] = set()
patched_api = False
missing_hint: list[str] = []

for path in candidates:
    if not path.is_file():
        continue
    try:
        resolved = path.resolve()
    except OSError:
        continue
    if resolved in seen:
        continue
    seen.add(resolved)
    text = path.read_text(encoding="utf-8")
    original = text
    if "api." not in text and "norbot_api" not in text:
        continue

    if "zone=norbot_ci" not in text:
        idx = text.rfind("limit_req_zone")
        if idx != -1:
            nl = text.find("\n", idx)
            text = text[: nl + 1] + zone_line + "\n" + text[nl + 1 :]
        else:
            text = zone_line + "\n" + text

    if "__norbot/ci-apply" not in text and "norbot-ci-apply.inc" not in text:
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
            # Insert before each api server's catch-all location / (proxy to API).
            def insert_before_api_root(match: re.Match[str]) -> str:
                prefix, loc = match.group(1), match.group(2)
                if "norbot-ci-apply.inc" in prefix or "__norbot/ci-apply" in prefix:
                    return match.group(0)
                return prefix + "\n" + include_line + "\n" + loc

            text2, n2 = re.subn(
                r"(server_name\s+api\.[^\n]+;\n(?:(?!\nserver\s*\{).)*?)(\n    location / \{)",
                insert_before_api_root,
                text,
                flags=re.S,
            )
            if n2:
                text = text2
            else:
                # Last resort: before any location / that proxies norbot_api.
                text3, n3 = re.subn(
                    r"(\n)(    location / \{\n(?:[^\n]*\n)*?        proxy_pass http://norbot_api;)",
                    r"\1" + include_line + r"\n\2",
                    text,
                    count=1,
                )
                if n3:
                    text = text3
                else:
                    missing_hint.append(str(path))

    if "__norbot/ci-apply" in text or "norbot-ci-apply.inc" in text:
        patched_api = True

    if text != original:
        bak = path.with_name(path.name + ".bak-ci-apply")
        if not bak.exists():
            bak.write_text(original, encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"Updated {path}")

if not patched_api:
    print(
        "ERROR: could not wire /__norbot/ci-apply into an api.* nginx server block.",
        file=sys.stderr,
    )
    if missing_hint:
        print("Add this line inside the api.norbot.io (and api.test) server block,", file=sys.stderr)
        print("immediately before `location /`:", file=sys.stderr)
        print(include_line, file=sys.stderr)
        for p in missing_hint:
            print(f"  file: {p}", file=sys.stderr)
    sys.exit(1)
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
  exit 1
fi

# Prove the public route hits the agent (405 Method Not Allowed on GET), not FastAPI.
PROBE_HOST="${CI_APPLY_PROBE_HOST:-api.norbot.io}"
if command -v curl >/dev/null 2>&1; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "https://${PROBE_HOST}/__norbot/ci-apply" || true)"
  if [[ "${code}" == "405" ]]; then
    echo "Probe OK: GET https://${PROBE_HOST}/__norbot/ci-apply → 405 (agent reachable)."
  elif [[ "${code}" == "404" ]]; then
    echo "WARNING: GET https://${PROBE_HOST}/__norbot/ci-apply → 404 (still FastAPI or missing route)." >&2
    echo "Check sites-enabled and Cloudflare; agent listens on 127.0.0.1:9277." >&2
  else
    echo "Probe HTTP ${code:-?} for https://${PROBE_HOST}/__norbot/ci-apply (expected 405)." >&2
  fi
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
