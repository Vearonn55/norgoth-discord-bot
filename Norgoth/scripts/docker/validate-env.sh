#!/usr/bin/env bash
# Fail fast when the VDS env file would crash-loop api/bot on compose up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/validate_env.py" "$@"
