#!/usr/bin/env bash
# Log the VDS Docker daemon into GHCR.
# CI passes a job-scoped token via GHCR_PULL_TOKEN (not written to a host file).
# Operators may instead store a packages:read PAT at GHCR_PULL_TOKEN_FILE
# for manual pull/rollback when no job token is present.
set -euo pipefail

TOKEN_FILE="${GHCR_PULL_TOKEN_FILE:-/opt/norbot/env/ghcr.pull.token}"
USER_NAME="${GHCR_PULL_USER:-}"

if [[ -n "${GHCR_PULL_TOKEN:-}" ]]; then
  if [[ -z "${USER_NAME}" ]]; then
    echo "GHCR_PULL_TOKEN is set but GHCR_PULL_USER is empty." >&2
    exit 1
  fi
  printf '%s' "${GHCR_PULL_TOKEN}" | docker login ghcr.io -u "${USER_NAME}" --password-stdin
  exit 0
fi

USER_NAME="${USER_NAME:-norbot-pull}"

if [[ ! -f "${TOKEN_FILE}" ]]; then
  echo "Missing GHCR_PULL_TOKEN and ${TOKEN_FILE}." >&2
  echo "Deploy workflows pass a job-scoped GHCR_PULL_TOKEN." >&2
  echo "For manual pull/rollback, create a packages:read PAT at that path (mode 600)." >&2
  exit 1
fi

tr -d '\r' < "${TOKEN_FILE}" | docker login ghcr.io -u "${USER_NAME}" --password-stdin
