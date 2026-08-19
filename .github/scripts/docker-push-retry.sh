#!/usr/bin/env bash
# Push images to GHCR with retries for secondary rate limits (HTTP 403).
# Usage: docker-push-retry.sh image[:tag] [image[:tag] ...]
set -euo pipefail

MAX_ATTEMPTS="${DOCKER_PUSH_MAX_ATTEMPTS:-5}"
BASE_DELAY="${DOCKER_PUSH_RETRY_SECONDS:-20}"
GAP="${DOCKER_PUSH_GAP_SECONDS:-8}"

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 image[:tag] [image[:tag] ...]" >&2
  exit 1
fi

push_one() {
  local image="$1"
  local attempt=1
  local delay="${BASE_DELAY}"
  while true; do
    if docker push "${image}"; then
      return 0
    fi
    if (( attempt >= MAX_ATTEMPTS )); then
      echo "::error::docker push failed after ${MAX_ATTEMPTS} attempts: ${image}" >&2
      return 1
    fi
    echo "docker push failed (attempt ${attempt}/${MAX_ATTEMPTS}) for ${image}; retrying in ${delay}s (GHCR secondary rate limits are transient)."
    sleep "${delay}"
    delay=$(( delay * 2 ))
    attempt=$(( attempt + 1 ))
  done
}

first=1
for image in "$@"; do
  if (( first == 0 )); then
    sleep "${GAP}"
  fi
  first=0
  push_one "${image}"
done
