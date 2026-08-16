"""Shared helpers for kb_cli command modules.

Deliberately not imported by kb (the top-level entry point) or by any subparser
registry -- only by individual command modules -- so there is no import cycle:
dependencies flow one way, from command modules down to here.
"""

import argparse
import sys
from typing import Any, Callable, Iterable, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from context import resolve_context
from mixins import HasUniqueName
from models import Context, EntityLink, HasContextOrTag, Journal, Tag
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


def scope_to_context(session: Session, context: Optional[Context]) -> Optional[Sequence[Context]]:
    """Print the "context: X"/"context: none" banner a read-scoped list/tree command is
    filtering by, then return the self_and_descendants scope for that context (or None for
    everywhere) -- so an explicit --context scoping never happens silently. See
    creation_context in context.py for the equivalent, stricter rule for `add` commands."""
    print(f"context: {context.name}" if context else "context: none", file=sys.stderr)
    return Context.self_and_descendants(session, context.name) if context else None


def check_no_links(session: Session, entity_type: str, entity_id: int, force: bool) -> None:
    """Refuse to delete a row that EntityLinks still point at, unless force is set -- the
    same "list blockers, require an explicit override flag" shape Instruction.cmd_delete
    already uses for child Instructions. Call this first thing in any cmd_delete; on force,
    it deletes the blocking links itself so the caller's own delete can proceed unguarded."""
    links = EntityLink.for_entity(session, entity_type, entity_id)
    if not links:
        return
    if not force:
        ids = ", ".join(str(link.id) for link in links)
        print(
            f"{entity_type}:{entity_id} has links (EntityLink id(s): {ids}) -- pass --force-delete-links "
            "to delete them first, or remove them yourself with `kb link rm ID`",
            file=sys.stderr,
        )
        sys.exit(1)
    for link in links:
        session.delete(link)


E = TypeVar("E")


def apply_text_edit(current: str, entity_label: str, append: Optional[str], replace: Optional[tuple[str, str]]) -> str:
    """Compute a new value for a large free-text field (Instruction.body, Note.body, a
    Goal/Todo's notes, ...) from a small delta instead of requiring the caller to resend
    the entire unchanged field -- the same motivation as preferring the Edit tool's
    old_string/new_string over rewriting a whole file for a one-line change.

    append adds a paragraph; replace substitutes one occurrence of (old, new), erroring
    (rather than guessing) if old is missing or not unique in the field -- exits the
    process directly, matching this module's existing get_by_name/apply_updates error
    style, since these are CLI-only helpers with no non-CLI caller today. Both append and
    replace's new value are routed through resolve_text_arg, so `--append -` / `--replace OLD -`
    read from stdin the same way any other free-text CLI arg does (root's stdin-body
    convention) -- append/replace text is exactly as likely to be long/multi-line as a plain
    --body value, so it should honor the same convention, not silently take the literal "-".
    Pass only one of append/replace -- the caller decides which, if either, applies."""
    if append is not None:
        append = resolve_text_arg(append)
        return f"{current}\n\n{append}" if current else append
    if replace is not None:
        old, new = replace
        new = resolve_text_arg(new)
        count = current.count(old)
        if count == 0:
            print(f"--replace: old text not found in {entity_label}", file=sys.stderr)
            sys.exit(1)
        if count > 1:
            print(
                f"--replace: old text appears {count} times in {entity_label} -- "
                "make it unique (more surrounding context) before replacing",
                file=sys.stderr,
            )
            sys.exit(1)
        return current.replace(old, new)
    return current


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


def describe_entity_ref(session: Session, entity_type: str, entity_id: int) -> str:
    """TYPE:ID plus that row's own __repr__/title, or a bare '(missing)' marker if the row
    is gone -- links themselves are never silently dropped when their target disappears
    outside kb's own delete guard (e.g. a manual DB edit), so traversal must tolerate it."""
    row = EntityLink.resolve(session, entity_type, entity_id)
    label = f"{entity_type}:{entity_id}"
    if row is None:
        return f"{label} (missing)"
    return f"{label} {row!r}"


def print_links(
    session: Session,
    entity_type: str,
    entity_id: int,
    other_filter: Optional[Callable[[str, int], bool]] = None,
) -> None:
    """Print every EntityLink touching (entity_type, entity_id), one hop out, the same
    format `kb link show` uses one level deep -- the automatic, always-on counterpart to
    that command's on-demand deeper traversal. Every `show` subcommand for a linkable
    entity calls this last, so a link is visible the moment its owning row is shown,
    without a separate `kb link show TYPE:ID` round trip. Silent when there are no links,
    matching print_journal_history's "say nothing if there's nothing to say" convention.

    other_filter, if given, is called with (other_type, other_id) for each linked row and
    only prints the ones it accepts -- e.g. Instruction's show command uses this to offer
    --instructions-only / --system-only display flags without duplicating this function."""
    links = EntityLink.for_entity(session, entity_type, entity_id)
    if not links:
        return
    pairs = sorted(((link.other_side(entity_type, entity_id), link) for link in links), key=lambda p: p[0])
    if other_filter is not None:
        pairs = [(other, link) for other, link in pairs if other_filter(*other)]
    if not pairs:
        return
    print(f"links: {len(pairs)}")
    for (other_type, other_id), link in pairs:
        arrow = (
            f"--{link.relation}-->" if (entity_type, entity_id) == (link.type_a, link.id_a) else f"<--{link.relation}--"
        )
        print(f"  {arrow} {describe_entity_ref(session, other_type, other_id)}")


def resolve_text_arg(value: str) -> str:
    """A free-text CLI arg (Note.body, Todo.title, a journal note, ...) whose value is the
    literal string "-" is read from stdin instead -- the standard Unix convention, so any long
    or special-character-laden body can be piped in (`kb notes add "title" - <<'EOF'` or
    `cmd | kb notes add "title" -`) instead of forcing it through shell argument quoting.
    Every `add`/`update` subcommand taking free-text should route its positional/flag value
    through this before use, the same shared-helper discipline as apply_text_edit above."""
    if value == "-":
        return sys.stdin.read()
    return value


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
