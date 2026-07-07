"""Todo operations."""
import argparse
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from context import resolve_context
from models import Journal, Todo, TodoStatus, TodoTag, WishlistEffort

from kb_cli._util import add_history_arg, get_by_name, print_journal_history


def _parse_defer_until(raw: str) -> datetime:
    now = datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        t = datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        raise SystemExit(f"--defer-until: could not parse {raw!r} (use HH:MM, 'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM')")
    candidate = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def cmd_show(args: argparse.Namespace) -> None:
    for i, todo_id in enumerate(args.ids):
        if i > 0:
            print()
        todo = args.session.get(Todo, todo_id)
        if todo is None:
            print(f"id: {todo_id}\nerror: not found", file=sys.stderr)
            continue
        print(f"id: {todo.id}")
        print(f"title: {todo.title}")
        print(f"status: {todo.status.value}")
        if todo.effort:
            print(f"effort: {todo.effort.value}")
        if todo.goal:
            print(f"goal: {todo.goal.title}")
        if todo.context:
            print(f"context: {todo.context.name}")
        if todo.blocked_by:
            print(f"blocked_by: #{todo.blocked_by.id} {todo.blocked_by.title} [{todo.blocked_by.status.value}]")
        if todo.tags:
            print(f"tags: {', '.join(t.name for t in todo.tags)}")
        if todo.notes:
            print(f"notes: {todo.notes}")

        print_journal_history(args.session, Journal, "Todo", todo.id, args.history, f"journal show Todo {todo.id} or kb todo show {todo.id} --history [N]")


def cmd_add(args: argparse.Namespace) -> None:
    effort = WishlistEffort(args.effort) if args.effort else None
    defer_until = _parse_defer_until(args.defer_until) if args.defer_until else None
    context = resolve_context(args.session, args.context)
    todo = Todo.create(args.session, args.title, notes=args.notes, effort=effort, defer_until=defer_until, context=context)
    args.session.commit()
    print(todo)


def cmd_update(args: argparse.Namespace) -> None:
    todo = args.session.get(Todo, args.id)
    if todo is None:
        print(f"Todo #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    if args.title is not None:
        todo.title = args.title
    if args.effort is not None:
        todo.effort = WishlistEffort(args.effort)
    if args.defer_until is not None:
        todo.defer_until = _parse_defer_until(args.defer_until)
    if args.notes is not None:
        todo.notes = args.notes
    if args.context is not None:
        todo.context = resolve_context(args.session, args.context)
    if args.goal is not None:
        todo.goal_id = args.goal
    args.session.commit()
    print(todo)


def cmd_complete(args: argparse.Namespace) -> None:
    for todo_id in args.ids:
        todo = args.session.get(Todo, todo_id)
        if todo is None:
            print(f"Todo #{todo_id}: not found", file=sys.stderr)
            continue
        todo.status = TodoStatus.DONE
        print(f"Todo #{todo_id}: {todo.title!r} -> done")
    args.session.commit()


def cmd_pending(args: argparse.Namespace) -> None:
    effort = WishlistEffort(args.effort) if args.effort else None
    tag = get_by_name(args.session, TodoTag, args.tag) if args.tag else None
    todos = Todo.pending(args.session, effort=effort, include_deferred=args.all, tag=tag)
    if not todos:
        print("No pending todos.")
        return
    now = datetime.now(timezone.utc)
    for t in todos:
        marker = ""
        if t.defer_until is not None:
            defer_until = t.defer_until.replace(tzinfo=timezone.utc) if t.defer_until.tzinfo is None else t.defer_until
            if defer_until > now:
                marker = f" (deferred until {defer_until.strftime('%Y-%m-%d %H:%M')})"
        print(f"{t!r}{marker}")


def cmd_tag(args: argparse.Namespace) -> None:
    todo = args.session.get(Todo, args.id)
    if todo is None:
        print(f"Todo #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    for name in args.tags:
        tag = args.session.scalars(select(TodoTag).where(TodoTag.name == name)).one_or_none()
        if tag is None:
            tag = TodoTag(name=name)
            args.session.add(tag)
            args.session.flush()
        if tag not in todo.tags:
            todo.tags.append(tag)
    args.session.commit()
    print(todo)


def cmd_untag(args: argparse.Namespace) -> None:
    todo = args.session.get(Todo, args.id)
    if todo is None:
        print(f"Todo #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    for name in args.tags:
        tag = get_by_name(args.session, TodoTag, name)
        if tag in todo.tags:
            todo.tags.remove(tag)
    args.session.commit()
    print(todo)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("todo", help="Todo operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show Todo details")
    p_show.add_argument("ids", nargs="+", type=int)
    add_history_arg(p_show)
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a Todo")
    p_add.add_argument("title")
    p_add.add_argument("--effort", choices=[e.value for e in WishlistEffort],
                        help="grab = quick/batchable, research = needs investigation, project = multi-step")
    p_add.add_argument("--defer-until", metavar="WHEN",
                        help="Hide from `todo pending`/summary until this time — HH:MM (today, or tomorrow if already past), "
                             "'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM'")
    p_add.add_argument("--notes")
    p_add.add_argument("--context", metavar="NAME", help="Act in context NAME for this command only")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Todo")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--title")
    p_update.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_update.add_argument("--defer-until", metavar="WHEN",
                           help="HH:MM (today, or tomorrow if already past), 'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM'")
    p_update.add_argument("--notes")
    p_update.add_argument("--context", metavar="NAME")
    p_update.add_argument("--goal", type=int, metavar="GOAL_ID")
    p_update.set_defaults(func=cmd_update)

    p_complete = sub.add_parser("complete", help="Mark Todo(s) done")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)

    p_pending = sub.add_parser("pending", help="List pending Todos, optionally filtered by effort/tag")
    p_pending.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_pending.add_argument("--tag", help="Only show Todos tagged with this (or a descendant of this) TodoTag")
    p_pending.add_argument("--all", action="store_true", help="Also include deferred Todos not yet due")
    p_pending.set_defaults(func=cmd_pending)

    p_tag = sub.add_parser("tag", help="Attach one or more tags to a Todo (creates tags that don't exist yet)")
    p_tag.add_argument("id", type=int)
    p_tag.add_argument("tags", nargs="+")
    p_tag.set_defaults(func=cmd_tag)

    p_untag = sub.add_parser("untag", help="Remove one or more tags from a Todo")
    p_untag.add_argument("id", type=int)
    p_untag.add_argument("tags", nargs="+")
    p_untag.set_defaults(func=cmd_untag)
