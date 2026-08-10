"""Backfill embed deployment ownership from role-menu bindings.

Deployments (``embed_message_deliveries``) default to ``owner_feature =
'embed_library'``. Any delivery a Self-Assignable Role menu is bound to should
be marked ``self_assignable_role`` so the Embed Library's generic Re-Sync never
recreates it as a plain (component-less) embed. Runtime detection already treats
bound deliveries as SAR-owned, so this script is an optional convenience that
makes the stored column accurate; correctness does not depend on it.

Idempotent: re-running only stamps deliveries not already marked.

Usage:
    python -m scripts.backfill_delivery_owner
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.embed_messages import EmbedMessageDelivery
from app.routes.role_menus import read_menus


async def main() -> None:
    factory = get_session_factory()
    stamped = 0
    async with factory() as session:
        guild_ids = (
            await session.scalars(
                select(EmbedMessageDelivery.guild_id).distinct()
            )
        ).all()

        for guild_id in guild_ids:
            try:
                menus = await read_menus(guild_id)
            except Exception:  # noqa: BLE001 - skip guilds with no/broken config
                continue

            bound_ids: set[str] = set()
            for menu in menus:
                if not isinstance(menu, dict):
                    continue
                if (menu.get("binding_type") or "standalone") != "embed_message":
                    continue
                delivery_id = str(menu.get("embed_delivery_id") or "").strip()
                if delivery_id:
                    bound_ids.add(delivery_id)

            if not bound_ids:
                continue

            deliveries = (
                await session.scalars(
                    select(EmbedMessageDelivery).where(
                        EmbedMessageDelivery.guild_id == guild_id
                    )
                )
            ).all()
            for delivery in deliveries:
                if (
                    str(delivery.id) in bound_ids
                    and delivery.owner_feature != "self_assignable_role"
                ):
                    delivery.owner_feature = "self_assignable_role"
                    stamped += 1

        if stamped:
            await session.commit()

    print(f"Stamped {stamped} deliveries as self_assignable_role.")


if __name__ == "__main__":
    asyncio.run(main())
