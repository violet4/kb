"""Log operations."""

import argparse
from datetime import datetime, timezone

from context import creation_context
from harness import current_session_id
from models import Context, LogEntry

from kb_cli._util import resolve_text_arg
from kb_cli.search import cmd_search_deprecated


def cmd_add(args: argparse.Namespace) -> None:
    occurred_at = None
    if args.date:
        occurred_at = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    entry = LogEntry.create(
        args.session,
        body=resolve_text_arg(args.body),
        domain=args.domain,
        context=creation_context(args),
        occurred_at=occurred_at,
    )
    args.session.commit()
    print(entry)


def cmd_flag(args: argparse.Namespace) -> None:
    """Thin front door onto `log add --domain claude-behavior` -- one word to type instead of a
    flag to recall, so flagging an observed phrase or behavior in the moment carries no friction.
    Not limited to language/phrasing -- any Claude habit or behavior worth tracking (a repeated
    workflow shortcut, an overused pattern, anything else worth analyzing later). See kb Goal #41."""
    entry = LogEntry.create(
        args.session,
        body=args.note,
        domain="claude-behavior",
        context=creation_context(args),
        source_ref=current_session_id(),
    )
    args.session.commit()
    print(entry)


def cmd_recent(args: argparse.Namespace) -> None:
    context = None
    if args.context_name:
        context, created = Context.get_or_create_reporting(args.session, args.context_name)
        if created:
            print(f"Created new top-level context {context.name!r} (see `kb context -h` to move/manage it).")
    entries = LogEntry.recent(args.session, domain=args.domain, context=context, limit=args.limit)
    if not entries:
        print("No entries.")
        return
    for e in entries:
        when = e.occurred_at.strftime("%Y-%m-%d %H:%M")
        domain = f" [{e.domain}]" if e.domain else ""
        print(f"#{e.id} {when}{domain}: {e.body}")


def add_flag_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Registers `kb flag` as its own top-level command (not nested under `log`), since the
    point is a one-word verb with nothing to recall -- see cmd_flag."""
    p_flag = subparsers.add_parser(
        "flag", help="Flag an observed Claude phrase or behavior for later analysis (see kb Goal #41)"
    )
    p_flag.add_argument("note", help="What was observed, e.g. 'found it' or 'skipped checking tests first'")
    p_flag.set_defaults(func=cmd_flag)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("log", aliases=["l"], help="Log operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a log entry")
    p_add.add_argument("body")
    p_add.add_argument("--domain", help="Loose category label, e.g. 'health', 'cat', 'work'")
    p_add.add_argument("--date", metavar="YYYY-MM-DD", help="Backdate the entry (default: now)")
    p_add.set_defaults(func=cmd_add)

    p_recent = sub.add_parser("recent", help="Show recent log entries")
    p_recent.add_argument("--domain", help="Only show this domain")
    p_recent.add_argument("--context", dest="context_name", help="Only show this context (default: all contexts)")
    p_recent.add_argument("--limit", type=int, default=20)
    p_recent.set_defaults(func=cmd_recent)

    p_search = sub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    p_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    p_search.set_defaults(func=cmd_search_deprecated)
