#!/bin/sh
# Drop to norbot after ensuring the uploads volume is writable.
set -eu
mkdir -p /app/var/uploads
if [ "$(id -u)" = "0" ]; then
  chown -R norbot:norbot /app/var/uploads || true
  exec gosu norbot "$@"
fi
exec "$@"
