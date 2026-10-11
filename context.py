"""Single implementation of turning a user-typed context/tag name into a Context or Tag.

Two distinct questions, two distinct functions -- never conflate them:
- Reading/scoping ("what should `todo list`/`context tree`/`kb summary` show me"):
  resolve_context() -- a command's own `--context NAME` narrows to that Context's subtree;
  without it, None means "everywhere". Every caller prints what it resolved to.
- Placing a new row ("where does this new Todo/Note/... belong"): resolve_placement() --
  every `add` command takes the placement as its first positional argument: a context
  name, or `#TAG` for a row that floats to every context carrying that tag. `inbox` is a
  real context like any other, for rows whose home isn't decided yet.

Neither ever creates a Context: an unknown name is a PlacementError listing the closest
existing names and the `kb context add` command that would create it, so a typo can never
grow the tree. Contexts are created only by `kb context add`.

Every script that needs a context from a name calls one of these, not Context directly.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Optional, Sequence, Type, TypeVar, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Context, Tag

INBOX_CONTEXT_NAME = "inbox"

TAG_PREFIX = "#"


class PlacementError(ValueError):
    """A context/tag name that doesn't exist. The message is complete user-facing text."""


_Named = TypeVar("_Named", Context, Tag)


def _find(session: Session, cls: Type[_Named], name: str) -> _Named:
    """Exact name, else the one case-insensitive match, else PlacementError with suggestions."""
    exact = session.scalars(select(cls).where(cls.name == name, cls.deleted_at.is_(None))).one_or_none()
    if exact is not None:
        return exact
    folded = session.scalars(select(cls).where(func.lower(cls.name) == name.lower(), cls.deleted_at.is_(None))).all()
    if len(folded) == 1:
        return folded[0]
    names = session.scalars(select(cls.name).where(cls.deleted_at.is_(None))).all()
    raise PlacementError(_unknown_message(cls, name, names))


def _unknown_message(cls: Union[Type[Context], Type[Tag]], name: str, names: Sequence[str]) -> str:
    by_lower = {n.lower(): n for n in names}
    close = [by_lower[n] for n in difflib.get_close_matches(name.lower(), list(by_lower), n=5, cutoff=0.6)]
    close += [n for n in names if name.lower() in n.lower() and n not in close][: 5 - len(close)]
    kind = "context" if cls is Context else "tag"
    lines = [f"no such {kind}: {name!r}"]
    if close:
        prefix = TAG_PREFIX if cls is Tag else ""
        lines.append("did you mean: " + ", ".join(f"{prefix}{n}" for n in close))
    if cls is Context:
        lines.append(f"to create it: kb context add {name!r} --parent PARENT   (see `kb context tree`)")
    else:
        lines.append(f"to create it: kb context tag CONTEXT {name!r}")
    return "\n".join(lines)


def find_context(session: Session, name: str) -> Context:
    """The Context a user typed by name; PlacementError with suggestions if there is none."""
    return _find(session, Context, name)


def resolve_context(session: Session, name: Optional[str]) -> Optional[Context]:
    """The Context a read-scoped command's `--context NAME` names, or None ("everywhere")."""
    return find_context(session, name) if name is not None else None


@dataclass(frozen=True)
class Placement:
    """Where a new row belongs: exactly one of context/tag is set."""

    context: Optional[Context]
    tag: Optional[Tag]

    @property
    def label(self) -> str:
        return f"{TAG_PREFIX}{self.tag.name}" if self.tag is not None else self.context.name  # type: ignore[union-attr]


def resolve_placement(session: Session, value: str) -> Placement:
    """An `add` command's positional CONTEXT argument: a context name, or `#TAG`."""
    if value.startswith(TAG_PREFIX):
        return Placement(context=None, tag=_find(session, Tag, value[len(TAG_PREFIX) :]))
    return Placement(context=_find(session, Context, value), tag=None)


def resolve_context_only(session: Session, value: str) -> Context:
    """resolve_placement for rows that can't float on a tag (Note, LogEntry)."""
    if value.startswith(TAG_PREFIX):
        raise PlacementError(f"{value!r}: this record needs a context, not a tag")
    return _find(session, Context, value)


def get_inbox_context(session: Session) -> Context:
    """The fixed `inbox` Context: the default placement in the web UI's quick-capture forms."""
    return Context.get_or_create(session, INBOX_CONTEXT_NAME)
