"""Alembic revision ids must fit alembic_version.version_num."""

from __future__ import annotations

import re
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations" / "versions"
REVISION_RE = re.compile(
    r'^revision(?:\s*:\s*[^=]+)?\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
ALEMBIC_VERSION_NUM_MAX_LENGTH = 32


def test_alembic_revision_ids_fit_varchar_32() -> None:
    """Postgres alembic_version.version_num is VARCHAR(32); longer ids fail upgrade."""

    too_long: list[tuple[str, str, int]] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        match = REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match is not None, f"{path.name} is missing a revision assignment"
        revision = match.group(1)
        if len(revision) > ALEMBIC_VERSION_NUM_MAX_LENGTH:
            too_long.append((path.name, revision, len(revision)))

    assert too_long == [], (
        "Alembic revision ids must be <= 32 characters: "
        + ", ".join(f"{name}={revision!r} ({length})" for name, revision, length in too_long)
    )
