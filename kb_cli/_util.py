"""Shared helpers for kb_cli command modules.

Deliberately not imported by kb (the top-level entry point) or by any subparser
registry -- only by individual command modules -- so there is no import cycle:
dependencies flow one way, from command modules down to here.
"""

import argparse
import sys
from typing import Any, Iterable, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from context import resolve_context
from mixins import HasUniqueName
from models import HasContextOrTag, Journal, Tag
from models_pg import PgItem

# SQLAlchemy declarative classes don't satisfy structural Protocol matching (their
# class-level attributes are InstrumentedAttribute, not the Mapped[T] written in the
# class body), so classes needing get_by_name inherit the real HasUniqueName mixin
# (nominal typing) instead. PgItem is the one exception: it gets `.name` from Item
# (not unique at the schema level, since multiple games can share item names), so it
# can't use the mixin -- named explicitly here instead.
_Named = HasUniqueName | PgItem
T = TypeVar("T", bound=_Named)


def get_by_name(sess: Session, cls: Type[T], name: str) -> T:
    """Look up a unique-named row (PgNpc, PgMob, PgPlayer, PgCharacter, ...) or exit with an error."""
    obj = sess.scalars(select(cls).where(cls.name == name)).one_or_none()
    if obj is None:
        print(f"{cls.__name__} {name!r}: not found", file=sys.stderr)
        sys.exit(1)
    return obj


E = TypeVar("E")


def apply_updates(session: Session, model: Type[E], entity_id: int, entity_label: str, fields: dict[str, Any]) -> E:
    """The one `cmd_update` body shared by every entity's update command: look up
    the row by id (exit with an error if missing) and set each attr whose new value
    isn't None. `fields` maps attr name -> already-transformed new value (enum
    coercion, parsing, etc. is the caller's job -- this only skips None entries and
    assigns the rest). Does not commit -- the caller commits once, after any further
    mutation (e.g. apply_context_or_tag_update) is applied in the same transaction."""
    row = session.get(model, entity_id)
    if row is None:
        print(f"{entity_label} #{entity_id}: not found", file=sys.stderr)
        sys.exit(1)
    for attr, value in fields.items():
        if value is not None:
            setattr(row, attr, value)
    return row


def apply_context_or_tag_update(
    session: Session, row: HasContextOrTag, new_context: Optional[str], new_tag: Optional[str]
) -> None:
    """Re-pin a HasContextOrTag row's context/tag after creation, the shared logic
    behind every entity's `update --context`/`--tag` flags. Setting one clears the
    other, matching HasContextOrTag's mutual-exclusivity validator."""
    if new_context is not None:
        row.tag = None
        row.context = resolve_context(session, new_context)
    if new_tag is not None:
        row.context = None
        row.tag = get_by_name(session, Tag, new_tag)


def print_fields(fields: Iterable[tuple[str, object]]) -> None:
    """Print (label, value) pairs, skipping None/empty values."""
    for label, value in fields:
        if value is not None and value != "":
            print(f"{label}: {value}")


def add_history_arg(parser: argparse.ArgumentParser) -> None:
    """Attach the shared --history [N] flag used by `show` subcommands with Journal history."""
    parser.add_argument(
        "--history",
        nargs="?",
        type=int,
        const=0,
        default=None,
        metavar="N",
        help="Expand journal history inline; optionally show only the last N entries",
    )


def print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    """Print rows as a column-aligned table, padded to fit terminal width."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    print(fmt(headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


def print_journal_history(
    session: Session,
    journal_cls: Type[Journal],
    entity_type: str,
    entity_id: int,
    history_arg: int | None,
    hint_cmd: str,
) -> None:
    """Print Journal history for an entity per the shared --history convention.

    history_arg is args.history: None (show a one-line hint if history exists),
    0 (show all), or N (show only the last N entries).
    """
    history = journal_cls.for_entity(session, entity_type, entity_id)
    if history_arg is not None:
        shown = history[-history_arg:] if history_arg else history
        for j, e in enumerate(shown):
            if j > 0:
                print()
            when = e.created_at.strftime("%Y-%m-%d %H:%M")
            if e.field:
                print(f"  [{when}] {e.field}: {e.old_value!r} -> {e.new_value!r}")
                if e.note:
                    print(f"    {e.note}")
            else:
                print(f"  [{when}] {e.note}")
    elif history:
        print(f"history: {len(history)} entries — {hint_cmd}")
