"""Seed a guild + verification configuration through the running API.

Usage (from Norgoth/apps/api, with the API running):

  .venv/bin/python scripts/seed_verification.py \
      --guild-id 123... --guild-name "My Server" --owner-id 456... \
      --verification-channel 111... --log-channel 222... \
      --verified-role 333... --unverified-role 444... --member-role 555...

If the bot is online, --guild-id/--guild-name/--owner-id can be omitted and
the first connected guild is used.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx
import redis

API_BASE_URL = "http://127.0.0.1:8000"
REDIS_URL = "redis://localhost:6379/0"


def discover_guild() -> tuple[str, str, str] | None:
    client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        raw = client.get("norgoth:bot:status")
    finally:
        client.close()

    if not raw:
        return None

    status = json.loads(raw)
    guilds = status.get("guilds") or []

    if not guilds:
        return None

    guild = guilds[0]
    resources_client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        resources_raw = resources_client.get(
            f"norgoth:guild:{guild['id']}:resources"
        )
    finally:
        resources_client.close()

    owner_id = "0"

    if resources_raw:
        # Owner ID is not in resources; the API upsert from the bot already
        # registered the guild, so any owner value here is only a fallback.
        owner_id = "0"

    return guild["id"], guild["name"], owner_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guild-id")
    parser.add_argument("--guild-name")
    parser.add_argument("--owner-id")
    parser.add_argument("--verification-channel", required=True)
    parser.add_argument("--log-channel", required=True)
    parser.add_argument("--verified-role", required=True)
    parser.add_argument("--unverified-role", required=True)
    parser.add_argument("--member-role", required=True)
    parser.add_argument("--min-account-age-days", type=int, default=7)
    parser.add_argument("--allow-vpn", action="store_true")
    parser.add_argument("--allow-shared-ip", action="store_true")
    args = parser.parse_args()

    guild_id = args.guild_id
    guild_name = args.guild_name
    owner_id = args.owner_id

    if not guild_id:
        discovered = discover_guild()

        if discovered is None:
            print(
                "No --guild-id given and the bot is not online. "
                "Provide --guild-id/--guild-name/--owner-id explicitly."
            )
            return 1

        guild_id, discovered_name, discovered_owner = discovered
        guild_name = guild_name or discovered_name
        owner_id = owner_id or discovered_owner
        print(f"Discovered guild from bot: {guild_name} ({guild_id})")

    with httpx.Client(base_url=API_BASE_URL, timeout=15.0) as client:
        guild_response = client.put(
            f"/api/v1/guilds/{guild_id}",
            json={
                "discord_guild_name": guild_name or "Unknown Guild",
                "discord_owner_id": owner_id or "0",
            },
        )
        print(f"Guild upsert: HTTP {guild_response.status_code}")

        if guild_response.status_code not in (200, 201):
            print(guild_response.text)
            return 1

        config_response = client.put(
            f"/api/v1/guilds/{guild_id}/configuration",
            json={
                "verification_channel_id": args.verification_channel,
                "log_channel_id": args.log_channel,
                "unverified_role_id": args.unverified_role,
                "member_role_id": args.member_role,
                "minimum_account_age_days": args.min_account_age_days,
                "session_timeout_seconds": 900,
                "deny_vpn_or_proxy": not args.allow_vpn,
                "deny_shared_ip": not args.allow_shared_ip,
                "enabled": True,
            },
        )
        print(f"Configuration upsert: HTTP {config_response.status_code}")

        if config_response.status_code not in (200, 201):
            print(config_response.text)
            return 1

    print("Seed complete. Verification authorize URL:")
    print(f"  {API_BASE_URL}/api/v1/oauth/discord/authorize/{guild_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
