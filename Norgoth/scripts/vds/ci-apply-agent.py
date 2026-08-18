#!/usr/bin/env python3
"""Loopback HMAC endpoint that runs apply-release.sh.

Listens on 127.0.0.1 only. Nginx on :443 forwards /__norbot/ci-apply here so
GitHub-hosted runners can deploy when inbound SSH is filtered.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND = os.environ.get("NORBOT_CI_APPLY_BIND", "127.0.0.1")
PORT = int(os.environ.get("NORBOT_CI_APPLY_PORT", "9277"))
SECRET_FILE = os.environ.get(
    "NORBOT_CI_APPLY_SECRET_FILE", "/opt/norbot/env/ci-apply.secret"
)
APPLY_SCRIPT = os.environ.get(
    "NORBOT_CI_APPLY_SCRIPT", "/opt/norbot/scripts/apply-release.sh"
)
LOCK_PATH = os.environ.get("NORBOT_CI_APPLY_LOCK", "/opt/norbot/ci-apply/apply.lock")
LOG_PATH = os.environ.get("NORBOT_CI_APPLY_LOG", "/opt/norbot/ci-apply/last.log")
MAX_SKEW_SEC = int(os.environ.get("NORBOT_CI_APPLY_SKEW", "120"))
APPLY_TIMEOUT_SEC = int(os.environ.get("NORBOT_CI_APPLY_TIMEOUT", "900"))
MAX_BODY = 16 * 1024


def _secret() -> bytes:
    with open(SECRET_FILE, "r", encoding="utf-8") as fh:
        value = fh.read().strip()
    if len(value) < 32:
        raise RuntimeError("ci-apply secret is too short")
    return value.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "norbot-ci-apply/1"

    def log_message(self, fmt: str, *args) -> None:
        # Do not log request bodies (may contain a GHCR token).
        sys_stderr = self.address_string()
        msg = fmt % args
        if "token" in msg.lower() or "secret" in msg.lower():
            msg = "[redacted]"
        print(f"{sys_stderr} {msg}", flush=True)

    def do_GET(self) -> None:
        self._send(405, {"ok": False, "error": "POST only"})

    def do_POST(self) -> None:
        if self.path not in ("/", "/__norbot/ci-apply"):
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400, {"ok": False, "error": "bad content-length"})
            return
        if length < 2 or length > MAX_BODY:
            self._send(413, {"ok": False, "error": "bad body size"})
            return
        body = self.rfile.read(length)
        ts_raw = self.headers.get("X-Norbot-Timestamp", "")
        sig = self.headers.get("X-Norbot-Signature", "")
        try:
            ts = int(ts_raw)
        except ValueError:
            self._send(401, {"ok": False, "error": "bad timestamp"})
            return
        if abs(time.time() - ts) > MAX_SKEW_SEC:
            self._send(401, {"ok": False, "error": "timestamp skew"})
            return
        try:
            secret = _secret()
        except OSError:
            self._send(500, {"ok": False, "error": "secret missing"})
            return
        expected = hmac.new(
            secret, f"{ts}.".encode("ascii") + body, hashlib.sha256
        ).hexdigest()
        got = sig.removeprefix("sha256=").strip()
        if not got or not hmac.compare_digest(expected, got):
            self._send(401, {"ok": False, "error": "bad signature"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"ok": False, "error": "invalid json"})
            return
        env_name = str(payload.get("env", ""))
        sha = str(payload.get("sha", "")).lower()
        owner = str(payload.get("owner", "")).lower()
        ghcr_user = str(payload.get("ghcr_user", ""))
        ghcr_token = str(payload.get("ghcr_token", ""))
        if env_name not in ("production", "test"):
            self._send(400, {"ok": False, "error": "invalid env"})
            return
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            self._send(400, {"ok": False, "error": "invalid sha"})
            return
        if not owner:
            self._send(400, {"ok": False, "error": "missing owner"})
            return

        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOCK_PATH, "a+", encoding="utf-8") as lock_fh:
            try:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self._send(409, {"ok": False, "error": "deploy already running"})
                return
            env = os.environ.copy()
            env["NORBOT_IMAGE_OWNER"] = owner
            if ghcr_token and ghcr_user:
                env["GHCR_PULL_TOKEN"] = ghcr_token
                env["GHCR_PULL_USER"] = ghcr_user
            try:
                with open(LOG_PATH, "w", encoding="utf-8") as log_fh:
                    proc = subprocess.run(
                        [APPLY_SCRIPT, env_name, sha],
                        env=env,
                        stdout=log_fh,
                        stderr=subprocess.STDOUT,
                        timeout=APPLY_TIMEOUT_SEC,
                        check=False,
                    )
            except FileNotFoundError:
                self._send(500, {"ok": False, "error": "apply-release.sh missing"})
                return
            except subprocess.TimeoutExpired:
                self._send(504, {"ok": False, "error": "apply timed out"})
                return
            tail = _log_tail()
            if proc.returncode != 0:
                self._send(
                    500,
                    {
                        "ok": False,
                        "error": f"apply exited {proc.returncode}",
                        "log_tail": tail,
                    },
                )
                return
            self._send(200, {"ok": True, "sha": sha, "env": env_name, "log_tail": tail})

    def _send(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def _log_tail(limit: int = 4000) -> str:
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read()
    except OSError:
        return ""
    return data[-limit:]


def main() -> None:
    _secret()
    httpd = ThreadingHTTPServer((BIND, PORT), Handler)
    httpd.daemon_threads = False
    print(f"ci-apply listening on {BIND}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
