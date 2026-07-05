"""Shared helpers for kb_cli command modules.

Deliberately not imported by kb (the top-level entry point) or by any subparser
registry -- only by individual command modules -- so there is no import cycle:
dependencies flow one way, from command modules down to here.
"""
import sys

from sqlalchemy import select


def get_by_name(sess, cls, name):
    """Look up a unique-named row (PgNpc, PgMob, PgPlayer, PgCharacter, ...) or exit with an error."""
    obj = sess.scalars(select(cls).where(cls.name == name)).one_or_none()
    if obj is None:
        print(f"{cls.__name__} {name!r}: not found", file=sys.stderr)
        sys.exit(1)
    return obj


def print_fields(fields):
    """Print (label, value) pairs, skipping None/empty values."""
    for label, value in fields:
        if value is not None and value != "":
            print(f"{label}: {value}")


def add_history_arg(parser):
    """Attach the shared --history [N] flag used by `show` subcommands with Journal history."""
    parser.add_argument(
        "--history", nargs="?", type=int, const=0, default=None,
        metavar="N", help="Expand journal history inline; optionally show only the last N entries",
    )


def print_journal_history(journal_cls, entity_type, entity_id, history_arg, hint_cmd):
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
