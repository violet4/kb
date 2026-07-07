"""Reusable trait mixins for game-specific side tables (JTI pattern — see models/games/*.py).

Compose only the traits a given game's items actually use, e.g.:
    class PzItem(Item, HasWeight): ...
    class PgItem(Item, HasStackSize): ...
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, Integer, String
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
    """Real-world-style weight, e.g. Project Zomboid."""

    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class HasGridSize:
    """Inventory-grid footprint, e.g. width x height in cells (Resident Evil/Diablo-style)."""

    grid_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grid_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class HasVolume:
    """Item's own volume, for games that track carry capacity by volume rather than weight."""

    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class HasContainerCapacity:
    """Max volume a container item can hold — distinct from the container's own volume (HasVolume)."""

    container_capacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class HasStackSize:
    """Max stack size, e.g. Project Gorgon."""

    max_stack_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
