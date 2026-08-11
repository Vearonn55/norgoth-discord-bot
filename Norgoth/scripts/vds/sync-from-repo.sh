#!/usr/bin/env bash
# Sync deploy manifests + scripts from the repo into /opt/norbot (on the VDS).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="${1:-/opt/norbot}"

mkdir -p "${TARGET}/deploy" "${TARGET}/scripts" "${TARGET}/releases" "${TARGET}/backups/postgres" "${TARGET}/env"

rsync -a --delete \
  "${REPO_ROOT}/Norgoth/deploy/" \
  "${TARGET}/deploy/"

rsync -a \
  "${REPO_ROOT}/Norgoth/scripts/docker/" \
  "${TARGET}/scripts/"

chmod +x "${TARGET}/scripts/"*.sh
echo "Synced deploy + scripts into ${TARGET}"
