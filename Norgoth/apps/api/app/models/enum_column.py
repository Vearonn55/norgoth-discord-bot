"""Shared helper for mapping Python ``StrEnum`` values to a portable column.

The project stores enums as ``VARCHAR`` + ``CHECK`` (non-native) rather than
native PostgreSQL enum types. Native enums require fragile ``ALTER TYPE``
migrations to add values; the CHECK-constraint approach keeps schema changes to
ordinary column alterations while still validating values at the database. This
helper centralises the exact ``Enum(...)`` configuration so every model declares
enum columns identically.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum

_EnumT = TypeVar("_EnumT", bound=StrEnum)


def str_enum(enum_cls: type[_EnumT], name: str, *, length: int = 32) -> Enum:
    """Return a non-native, CHECK-constrained ``Enum`` column type.

    Args:
        enum_cls: The Python ``StrEnum`` subclass to persist.
        name: The CHECK constraint name (kept stable across migrations).
        length: The backing ``VARCHAR`` length.
    """

    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum_type: [member.value for member in enum_type],
        length=length,
    )
