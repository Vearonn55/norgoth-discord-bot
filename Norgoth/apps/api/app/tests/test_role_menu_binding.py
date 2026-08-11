"""Tests for role-menu component building and embed-binding reconcile helpers."""

from types import SimpleNamespace
from uuid import uuid4

from app.routes.embed_messages import _changed_deliveries
from app.routes.role_menus import build_role_components

_ROLES = [
    {"role_id": "111", "label": "Red", "mode": "toggle", "style": "primary"},
    {"role_id": "222", "label": "Blue", "mode": "give", "style": "secondary"},
]


def test_build_buttons_components() -> None:
    """Buttons build action rows with prefixed custom ids per role."""

    components = build_role_components("menu-1", "buttons", _ROLES)

    assert components[0]["type"] == 1
    buttons = components[0]["components"]
    assert buttons[0]["custom_id"] == "norgoth:rolemenu:toggle:111"
    assert buttons[1]["custom_id"] == "norgoth:rolemenu:give:222"


def test_build_select_components() -> None:
    """Select builds a single string-select with mode:role_id option values."""

    components = build_role_components("menu-1", "select", _ROLES)

    select = components[0]["components"][0]
    assert select["type"] == 3
    assert select["custom_id"] == "norgoth:rolemenu:select:menu-1"
    values = [option["value"] for option in select["options"]]
    assert values == ["toggle:111", "give:222"]


def test_build_reactions_has_no_components() -> None:
    """Reaction menus carry no message components."""

    assert build_role_components("menu-1", "reactions", _ROLES) == []


def test_changed_deliveries_detects_new_and_repointed_messages() -> None:
    """Only deliveries whose message id changed (or is new) are returned."""

    unchanged_id = uuid4()
    repointed_id = uuid4()
    new_id = uuid4()

    message = SimpleNamespace(
        deliveries=[
            SimpleNamespace(
                id=unchanged_id,
                channel_id="900",
                discord_message_id="msg-unchanged",
            ),
            SimpleNamespace(
                id=repointed_id,
                channel_id="901",
                discord_message_id="msg-new",
            ),
            SimpleNamespace(
                id=new_id,
                channel_id="902",
                discord_message_id="msg-fresh",
            ),
            SimpleNamespace(
                id=uuid4(),
                channel_id="903",
                discord_message_id=None,
            ),
        ]
    )

    prior = {
        str(unchanged_id): "msg-unchanged",
        str(repointed_id): "msg-old",
    }

    changed = _changed_deliveries(message, prior)

    assert str(unchanged_id) not in changed
    assert changed[str(repointed_id)] == ("901", "msg-new")
    assert changed[str(new_id)] == ("902", "msg-fresh")
    assert len(changed) == 2
