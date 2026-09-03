"""EN/TR localization for Discord command metadata and runtime replies."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import discord
from discord import app_commands, Locale
from discord.app_commands import TranslationContextTypes, locale_str

logger = logging.getLogger("norgoth.bot.commands.i18n")

_I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
_CATALOGS: dict[str, dict[str, str]] = {}


def _load_catalog(code: str) -> dict[str, str]:
    if code in _CATALOGS:
        return _CATALOGS[code]

    path = _I18N_DIR / f"{code}.json"
    data: dict[str, str] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = {str(k): str(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load i18n catalog %s", path)
    _CATALOGS[code] = data
    return data


def locale_code(locale: Locale | str | None) -> str:
    if locale is None:
        return "en"
    value = str(locale)
    if value.lower().startswith("tr"):
        return "tr"
    return "en"


def t(key: str, locale: Locale | str | None = None, **kwargs: Any) -> str:
    """Translate a runtime message key with EN fallback."""

    code = locale_code(locale)
    catalog = _load_catalog(code)
    fallback = _load_catalog("en")
    template = catalog.get(key) or fallback.get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def L(key: str) -> locale_str:
    """Mark a command description/name for Discord Translator lookup."""

    return locale_str(key)


class NorBotTranslator(app_commands.Translator):
    async def load(self) -> None:
        _load_catalog("en")
        _load_catalog("tr")

    async def unload(self) -> None:
        _CATALOGS.clear()

    async def translate(
        self,
        string: locale_str,
        locale: Locale,
        context: TranslationContextTypes,
    ) -> str | None:
        del context  # unused — keys are explicit
        code = locale_code(locale)
        if code == "en":
            # Prefer English catalog value; fall back to key message.
            en = _load_catalog("en")
            return en.get(string.message, string.message)
        catalog = _load_catalog(code)
        return catalog.get(string.message)
