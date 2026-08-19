#!/usr/bin/env python3
"""Fail fast when a VDS env file would crash-loop api/bot on compose up.

Prints which keys are set/unset — never prints secret values.
"""

from __future__ import annotations

import sys
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value.strip()
    return values


def present(values: dict[str, str], key: str) -> bool:
    return bool(values.get(key, "").strip())


def validate_env_file(env_name: str, env_file: Path) -> list[str]:
    if env_name not in {"production", "test"}:
        return [f"Unknown environment {env_name!r}."]
    if not env_file.is_file():
        return [
            f"{env_file} is missing. Copy deploy/env/{env_name}.env.example and fill secrets."
        ]

    values = parse_env(env_file.read_text(encoding="utf-8"))
    oauth_keys = (
        "NORGOTH_DISCORD_CLIENT_ID",
        "NORGOTH_DISCORD_CLIENT_SECRET",
        "NORGOTH_DISCORD_REDIRECT_URI",
    )
    oauth_set = [key for key in oauth_keys if present(values, key)]
    errors: list[str] = []

    if not present(values, "DISCORD_BOT_TOKEN"):
        errors.append(
            "DISCORD_BOT_TOKEN is empty. The bot container exits immediately without it."
        )

    if len(oauth_set) not in {0, 3}:
        errors.append(
            "Discord OAuth must be all-or-none. "
            "A leftover REDIRECT_URI with empty CLIENT_ID/SECRET aborts API boot."
        )
        for key in oauth_keys:
            state = "set" if present(values, key) else "unset"
            errors.append(f"  {key}: {state}")
    elif len(oauth_set) == 0:
        errors.append(
            "Discord OAuth is blank. Staging/production compose overlays set "
            "NORGOTH_AUTH_ENFORCED=true, so dashboard login needs CLIENT_ID, "
            "CLIENT_SECRET, and REDIRECT_URI filled together."
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in {"production", "test"}:
        print("Usage: validate_env.py <production|test> <env-file>", file=sys.stderr)
        return 1

    env_name, env_path = args[0], Path(args[1])
    errors = validate_env_file(env_name, env_path)
    if errors:
        print(f"Invalid {env_name} env file: {env_path}", file=sys.stderr)
        for line in errors:
            print(line, file=sys.stderr)
        print(
            "Edit the file on the VDS (mode 600). Do not commit secrets. "
            "See Norgoth/deploy/env/test.env.example.",
            file=sys.stderr,
        )
        return 1

    print(f"Env preflight passed for {env_name} ({env_path}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
