"""HasContextOrTag: a row pinned to exactly one Context or Tag."""

from __future__ import annotations

from typing import Any, ClassVar, Optional, Sequence

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, validates

from models.context import Context, Tag


class HasContextOrTag:
    """A single tag_id, mutually exclusive with the entity's own context_id: a Goal/Todo/Daily/
    Idea is either pinned to one place (context_id) or floats to anywhere carrying a matching
    Tag (tag_id), never both -- see Context/Tag docstrings for why. Composed alongside each
    entity's own context_id column, which predates this mixin and stays entity-local -- declared
    here too (Optional[int], no mapped_column) purely so mypy knows every subclass provides it;
    the real column comes from the subclass's own mapped_column(..., ForeignKey("context.id")).
    context/tag (the relationship attributes, not the _id FK columns) are declared the same
    type-only way, so shared helpers (e.g. kb_cli._util.apply_context_or_tag_update) can assign
    through the mixin type -- the real relationship() comes from each subclass."""

    tag_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tag.id"), nullable=True)
    context_id: Mapped[Optional[int]]
    context: Mapped[Optional[Context]]
    tag: Mapped[Optional["Tag"]]

    # Every row says where it belongs: exactly one of context_id/tag_id, enforced in the
    # database. A subclass whose placement is genuinely optional sets this to False.
    _context_or_tag_required: ClassVar[bool] = True

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        if not cls._context_or_tag_required:
            return ()
        return (CheckConstraint("(context_id IS NULL) != (tag_id IS NULL)", name="context_xor_tag"),)

    @validates("tag_id")
    def _validate_tag_id(self, key: str, value: Optional[int]) -> Optional[int]:
        if value is not None and getattr(self, "context_id", None) is not None:
            raise ValueError(f"{type(self).__name__}: context_id and tag_id are mutually exclusive")
        return value

    @validates("context_id")
    def _validate_context_id(self, key: str, value: Optional[int]) -> Optional[int]:
        if value is not None and getattr(self, "tag_id", None) is not None:
            raise ValueError(f"{type(self).__name__}: context_id and tag_id are mutually exclusive")
        return value

    @classmethod
    def matches_contexts(cls, contexts: Sequence[Context]) -> Any:
        """The one 'is this row addressable from this set of Contexts' expression --
        true for a row pinned to one of these contexts directly (context_id), or floating
        via a tag_id any of these contexts carries (see Tag docstring). Every caller that
        needs this match (a subtree-scoped .active() query, a single-node tree render) should
        go through this instead of re-deriving the context_id/tag_id OR by hand."""
        ids = [c.id for c in contexts]
        tag_ids = Context.active_tag_ids(contexts)
        return cls.context_id.in_(ids) | cls.tag_id.in_(tag_ids)
