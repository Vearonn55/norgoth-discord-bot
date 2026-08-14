#!/usr/bin/env bash
# Log the VDS Docker daemon into GHCR with a host-stored pull-only credential.
# Do not pass job GITHUB_TOKEN onto the host.
set -euo pipefail

TOKEN_FILE="${GHCR_PULL_TOKEN_FILE:-/opt/norbot/env/ghcr.pull.token}"
USER_NAME="${GHCR_PULL_USER:-norbot-pull}"

if [[ ! -f "${TOKEN_FILE}" ]]; then
  echo "Missing ${TOKEN_FILE}." >&2
  echo "Create a GitHub PAT (or fine-grained token) with packages:read only," >&2
  echo "write it to that path (mode 600), and set GHCR_PULL_USER if needed." >&2
  exit 1
fi

cat "${TOKEN_FILE}" | docker login ghcr.io -u "${USER_NAME}" --password-stdin
