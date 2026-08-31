#!/usr/bin/env bash
# Record CURRENT/PREVIOUS immutable release metadata on the VDS.
set -euo pipefail

SHA="${1:-${NORBOT_IMAGE_TAG:-}}"
ENV_NAME="${2:-production}"
RELEASES_DIR="${NORBOT_RELEASES_DIR:-/opt/norbot/releases}"

if [[ -z "${SHA}" ]]; then
  echo "Usage: $0 <git-sha> [production|test]" >&2
  exit 1
fi

mkdir -p "${RELEASES_DIR}"

CURRENT_FILE="${RELEASES_DIR}/CURRENT"
PREVIOUS_FILE="${RELEASES_DIR}/PREVIOUS"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -w "${RELEASES_DIR}" ]]; then
  echo "ERROR: ${RELEASES_DIR} is not writable by $(id -un)." >&2
  echo "On the VDS as root: chown -R norbot:norbot ${RELEASES_DIR}" >&2
  exit 1
fi

if [[ -f "${CURRENT_FILE}" ]]; then
  cp -f "${CURRENT_FILE}" "${PREVIOUS_FILE}"
fi

tmp="${CURRENT_FILE}.$$"
cat > "${tmp}" <<EOF
SHA=${SHA}
TIMESTAMP=${STAMP}
ENV=${ENV_NAME}
EOF
mv -f "${tmp}" "${CURRENT_FILE}"

echo "Recorded release SHA=${SHA} ENV=${ENV_NAME}"
cat "${CURRENT_FILE}"
