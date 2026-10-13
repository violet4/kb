"""Column mixins shared by several models."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column


class HasUniqueName:
    """A unique `name` column, for entities looked up by name (kb_cli._util.get_by_name).

    A plain mixin, not a typing.Protocol -- SQLAlchemy declarative classes don't satisfy
    structural Protocol matching (their class-level attributes are InstrumentedAttribute,
    not the Mapped[T] written in the class body), so a TypeVar needs a real, inherited
    base to bind against instead. See kb-engineering note on this for the full story.
    """

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class HasWeight:
    """An item's physical weight."""

    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
