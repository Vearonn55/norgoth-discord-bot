"""Simplify verification roles to Unverified + Base Member.

Verification now converges on a two-role transition: remove the Unverified role
and grant the base Member role on success. The separate ``verified`` role is
removed. To avoid losing configured data, any guild that has a ``verified``
binding but no (or empty) ``member`` binding has its verified role_id migrated
into the ``member`` binding first. Then all ``verified`` bindings are deleted and
the ``guild_role_bindings.purpose`` CHECK constraint is narrowed to drop
``verified``.

Revision ID: 0011_drop_verified_role
Revises: 0010_normalize_verif_state
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_drop_verified_role"
down_revision: str | Sequence[str] | None = "0010_normalize_verif_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""

    # 1) Preserve configured data: where a guild has a verified binding but no
    #    usable member binding, promote the verified role into the member slot.
    #    (a) Update an existing empty/blank member binding in place.
    op.execute(
        """
        UPDATE guild_role_bindings AS m
        SET role_id = v.role_id
        FROM guild_role_bindings AS v
        WHERE v.guild_id = m.guild_id
          AND v.purpose = 'verified'
          AND m.purpose = 'member'
          AND (m.role_id IS NULL OR m.role_id = '')
          AND v.role_id IS NOT NULL AND v.role_id <> ''
        """
    )
    #    (b) Insert a member binding cloned from verified where none exists.
    op.execute(
        """
        INSERT INTO guild_role_bindings (id, guild_id, purpose, role_id, created_at, updated_at)
        SELECT gen_random_uuid(), v.guild_id, 'member', v.role_id, now(), now()
        FROM guild_role_bindings AS v
        WHERE v.purpose = 'verified'
          AND v.role_id IS NOT NULL AND v.role_id <> ''
          AND NOT EXISTS (
              SELECT 1 FROM guild_role_bindings AS m
              WHERE m.guild_id = v.guild_id AND m.purpose = 'member'
          )
        """
    )

    # 2) Remove the now-obsolete verified bindings.
    op.execute("DELETE FROM guild_role_bindings WHERE purpose = 'verified'")

    # 3) Narrow the non-native enum CHECK constraint to drop 'verified'.
    op.execute(
        "ALTER TABLE guild_role_bindings "
        "DROP CONSTRAINT IF EXISTS ck_guild_role_bindings_guild_role_purpose"
    )
    op.execute(
        "ALTER TABLE guild_role_bindings "
        "ADD CONSTRAINT ck_guild_role_bindings_guild_role_purpose "
        "CHECK (purpose IN ('unverified', 'member', 'manual_review'))"
    )


def downgrade() -> None:
    """Revert this migration (re-allow 'verified'; data is not restored)."""

    op.execute(
        "ALTER TABLE guild_role_bindings "
        "DROP CONSTRAINT IF EXISTS ck_guild_role_bindings_guild_role_purpose"
    )
    op.execute(
        "ALTER TABLE guild_role_bindings "
        "ADD CONSTRAINT ck_guild_role_bindings_guild_role_purpose "
        "CHECK (purpose IN ('verified', 'unverified', 'member', 'manual_review'))"
    )
