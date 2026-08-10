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

if [[ -f "${CURRENT_FILE}" ]]; then
  cp "${CURRENT_FILE}" "${PREVIOUS_FILE}"
fi

cat > "${CURRENT_FILE}" <<EOF
SHA=${SHA}
TIMESTAMP=${STAMP}
ENV=${ENV_NAME}
EOF

echo "Recorded release SHA=${SHA} ENV=${ENV_NAME}"
cat "${CURRENT_FILE}"
