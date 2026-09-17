"""`kb win` -- completed work that was never tracked as a pending Todo. A win IS a Todo: the
only thing distinguishing it is that it never passed through TodoStatus.PENDING/IN_PROGRESS --
it was conceived, done, and finished in one sitting, so it's created and marked DONE in the
same action rather than needing a separate `todo complete` step. This reuses Todo's existing
title/notes/context/effort/embedding machinery instead of a bespoke shape, so a win is a
first-class Todo everywhere Todo already works (kb search, context tree, journal, links) --
it's simply invisible to `todo pending`/`Todo.active()` because those already filter to
PENDING/IN_PROGRESS, exactly like any other already-done Todo."""

import argparse
from datetime import datetime, timedelta, timezone

from context import creation_context
from models import Context, Todo, TodoStatus

from kb_cli._util import get_by_name, resolve_text_arg


def cmd_win_add(args: argparse.Namespace) -> None:
    todo = Todo.create(
        args.session,
        resolve_text_arg(args.title),
        notes=resolve_text_arg(args.body) if args.body else None,
        context=creation_context(args),
    )
    todo.status = TodoStatus.DONE
    if args.date:
        todo.created_at = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    args.session.commit()
    print(todo)


def cmd_win_recent(args: argparse.Namespace) -> None:
    """What got done recently -- --days N (default 7) resolves to a since-cutoff at UTC
    midnight N-1 days ago, matching the old log-backed win recent's semantics."""
    context = None
    if args.context_name:
        context = get_by_name(args.session, Context, args.context_name)
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=args.days - 1
    )
    todos = Todo.recently_completed(args.session, since, context=context, limit=args.limit)
    if not todos:
        print(f"No wins in the last {args.days} day(s).")
        return
    for t in reversed(todos):
        when = t.updated_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M")
        print(f"#{t.id} {when}: {t.title}")


def add_win_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Registers `kb win` as its own top-level command -- a one-word verb for the common case
    (record a completed piece of work), plus a dedicated `recent` query surface, matching
    every other add-shaped command's TITLE [BODY] convention (see resolve_text_arg for `-`
    stdin support on either)."""
    p_win = subparsers.add_parser("win", help="Track completed work not tied to a pending Todo/Goal (backed by Todo)")
    sub = p_win.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Record a completed piece of work")
    p_add.add_argument("title", help="What got done, e.g. 'Diagnosed THUM USB sensor as hardware-faulty'")
    p_add.add_argument("body", nargs="?", default=None, help="Longer explanation, e.g. how/why (optional)")
    p_add.add_argument("--date", metavar="YYYY-MM-DD", help="Backdate the entry (default: now)")
    p_add.set_defaults(func=cmd_win_add)

    p_recent = sub.add_parser("recent", help="What got done recently?")
    p_recent.add_argument(
        "--days", type=int, default=7, help="How many calendar days back, including today (default: 7)"
    )
    p_recent.add_argument("--context", dest="context_name", help="Only show this context (default: all contexts)")
    p_recent.add_argument("--limit", type=int, default=50)
    p_recent.set_defaults(func=cmd_win_recent)
