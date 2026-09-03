"""Export COMMANDS registry to Norgoth/docs/commands.md."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.commands.registry import (  # noqa: E402
    COMMAND_MANIFEST_VERSION,
    COMMANDS,
    commands_for_help,
)


def main() -> None:
    by_category: dict[str, list] = defaultdict(list)
    for spec in commands_for_help():
        by_category[spec.category].append(spec)

    lines = [
        "# NorBot Discord commands",
        "",
        f"Generated from the bot command registry (`COMMAND_MANIFEST_VERSION={COMMAND_MANIFEST_VERSION}`).",
        "",
        "Do not edit by hand — run:",
        "",
        "```bash",
        "python Norgoth/apps/bot/scripts/export_command_docs.py",
        "```",
        "",
    ]

    for category in (
        "General",
        "Info",
        "Levels",
        "Moderation",
        "Tickets",
        "Invites",
        "Verification",
        "Campaigns",
    ):
        specs = by_category.get(category)
        if not specs:
            continue
        lines.append(f"## {category}")
        lines.append("")
        lines.append("| Command | Description | Module | Visibility |")
        lines.append("|---|---|---|---|")
        for spec in specs:
            module = spec.module or "—"
            lines.append(
                f"| `/{spec.name}` | {spec.description} | `{module}` | {spec.visibility} |"
            )
        lines.append("")

    context = [s for s in COMMANDS if s.command_type == "user"]
    if context:
        lines.append("## Context menus (user)")
        lines.append("")
        lines.append("| Name | Description | Module |")
        lines.append("|---|---|---|")
        for spec in context:
            module = spec.module or "—"
            lines.append(f"| {spec.name} | {spec.description} | `{module}` |")
        lines.append("")

    out = ROOT / "docs" / "commands.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Force LF so Windows checkouts do not trip Linux CI git-diff.
    out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
