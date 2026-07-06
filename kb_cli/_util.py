"""Shared helpers for kb_cli command modules.

Deliberately not imported by kb (the top-level entry point) or by any subparser
registry -- only by individual command modules -- so there is no import cycle:
dependencies flow one way, from command modules down to here.
"""
import argparse
import sys
from typing import Iterable, Protocol, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session

from models import Journal


class _HasName(Protocol):
    name: Mapped[str]


T = TypeVar("T", bound=_HasName)


def get_by_name(sess: Session, cls: Type[T], name: str) -> T:
    """Look up a unique-named row (PgNpc, PgMob, PgPlayer, PgCharacter, ...) or exit with an error."""
    obj = sess.scalars(select(cls).where(cls.name == name)).one_or_none()
    if obj is None:
        print(f"{cls.__name__} {name!r}: not found", file=sys.stderr)
        sys.exit(1)
    return obj


def print_fields(fields: Iterable[tuple[str, object]]) -> None:
    """Print (label, value) pairs, skipping None/empty values."""
    for label, value in fields:
        if value is not None and value != "":
            print(f"{label}: {value}")


def add_history_arg(parser: argparse.ArgumentParser) -> None:
    """Attach the shared --history [N] flag used by `show` subcommands with Journal history."""
    parser.add_argument(
        "--history", nargs="?", type=int, const=0, default=None,
        metavar="N", help="Expand journal history inline; optionally show only the last N entries",
    )


def print_journal_history(journal_cls: Type[Journal], entity_type: str, entity_id: int,
                          history_arg: int | None, hint_cmd: str) -> None:
    """Print Journal history for an entity per the shared --history convention.

    history_arg is args.history: None (show a one-line hint if history exists),
    0 (show all), or N (show only the last N entries).
    """
    history = journal_cls.for_entity(entity_type, entity_id)
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
