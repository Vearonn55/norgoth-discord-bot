"""Backfill member_xp + ``:xp:text`` from legacy Redis total ``:xp`` ZSETs.

Pre-split XP lived only on ``norgoth:guild:{id}:xp``. After the text/voice
split, dashboard Text leaderboards rebuild from Postgres ``text_xp`` / Redis
``:xp:text``. This script attributes historical totals to text XP.

Idempotent: skips users who already have ``text_xp > 0`` in Postgres unless
``--force`` is passed.

Usage:
    python -m scripts.backfill_member_xp_from_redis
    python -m scripts.backfill_member_xp_from_redis --force
"""

from __future__ import annotations

import argparse
import asyncio
import re

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.runtime_events import MemberXp
from app.services.campaign_store import get_redis

GUILD_XP_RE = re.compile(r"^norgoth:guild:(\d+):xp$")


async def backfill(*, force: bool = False) -> None:
    redis = await get_redis()
    factory = get_session_factory()
    updated = 0
    skipped = 0

    try:
        cursor = 0
        keys: list[str] = []
        while True:
            cursor, batch = await redis.scan(cursor, match="norgoth:guild:*:xp", count=200)
            for key in batch:
                if GUILD_XP_RE.match(str(key)):
                    keys.append(str(key))
            if cursor == 0:
                break

        for key in keys:
            match = GUILD_XP_RE.match(key)
            if not match:
                continue
            guild_id = match.group(1)
            members = await redis.zrevrange(key, 0, -1, withscores=True)
            if not members:
                continue

            async with factory() as session:
                for user_id, score in members:
                    xp_int = int(float(score))
                    if xp_int <= 0:
                        continue
                    uid = str(user_id)
                    row = (
                        await session.execute(
                            select(MemberXp)
                            .where(
                                MemberXp.guild_id == guild_id,
                                MemberXp.user_id == uid,
                            )
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if row is None:
                        session.add(
                            MemberXp(
                                guild_id=guild_id,
                                user_id=uid,
                                xp=xp_int,
                                text_xp=xp_int,
                                voice_xp=0,
                            )
                        )
                        await redis.zadd(
                            f"norgoth:guild:{guild_id}:xp:text", {uid: float(xp_int)}
                        )
                        updated += 1
                    elif force or row.text_xp <= 0:
                        row.text_xp = xp_int if force or row.text_xp <= 0 else row.text_xp
                        if force:
                            row.text_xp = xp_int
                            row.voice_xp = 0
                            row.xp = xp_int
                        else:
                            row.text_xp = xp_int
                            row.xp = max(row.xp, xp_int + row.voice_xp)
                        await redis.zadd(
                            f"norgoth:guild:{guild_id}:xp:text",
                            {uid: float(row.text_xp)},
                        )
                        updated += 1
                    else:
                        skipped += 1
                await session.commit()
    finally:
        await redis.aclose()

    print(f"backfill_member_xp_from_redis: updated={updated} skipped={skipped}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing text_xp with Redis total (destructive).",
    )
    args = parser.parse_args()
    asyncio.run(backfill(force=args.force))


if __name__ == "__main__":
    main()
