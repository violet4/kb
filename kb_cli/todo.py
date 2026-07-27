"""Todo operations."""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from context import creation_context
from kb_cli.context_cmd import render_tree
from models import Journal, Tag, Todo, TodoStatus, WishlistEffort

from kb_cli._util import (
    add_history_arg,
    apply_context_or_tag_update,
    apply_updates,
    get_by_name,
    print_journal_history,
    scope_to_context,
)
from kb_cli.search import cmd_search


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
        if todo.tag:
            print(f"tag: {todo.tag.name}")
        if todo.blocked_by:
            print(f"blocked_by: #{todo.blocked_by.id} {todo.blocked_by.title} [{todo.blocked_by.status.value}]")
        if todo.notes:
            print(f"notes: {todo.notes}")

        print_journal_history(
            args.session,
            Journal,
            "Todo",
            todo.id,
            args.history,
            f"journal show Todo {todo.id} or kb todo show {todo.id} --history [N]",
        )


def cmd_add(args: argparse.Namespace) -> None:
    if args.tag and args.context_explicit:
        print("--tag and --context are mutually exclusive", file=sys.stderr)
        sys.exit(2)
    effort = WishlistEffort(args.effort) if args.effort else None
    defer_until = _parse_defer_until(args.defer_until) if args.defer_until else None
    tag = get_by_name(args.session, Tag, args.tag) if args.tag else None
    todo = Todo.create(
        args.session,
        args.title,
        notes=args.notes,
        effort=effort,
        defer_until=defer_until,
        context=None if tag else creation_context(args),
        tag=tag,
    )
    args.session.commit()
    print(todo)


def cmd_update(args: argparse.Namespace) -> None:
    todo = apply_updates(
        args.session,
        Todo,
        args.id,
        "Todo",
        {
            "title": args.title,
            "effort": WishlistEffort(args.effort) if args.effort else None,
            "defer_until": _parse_defer_until(args.defer_until) if args.defer_until else None,
            "notes": args.notes,
            "goal_id": args.goal,
        },
    )
    apply_context_or_tag_update(args.session, todo, args.new_context, args.new_tag)
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
    todos = Todo.active(args.session, effort=effort, include_deferred=args.all)
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


def cmd_list(args: argparse.Namespace) -> None:
    effort = WishlistEffort(args.effort) if args.effort else None
    if args.all:
        todos = Todo.active(args.session, effort=effort, include_deferred=args.include_deferred)
    else:
        in_scope = scope_to_context(args.session, args.context)
        todos = Todo.active(
            args.session,
            contexts=in_scope,
            include_no_context=True,
            effort=effort,
            include_deferred=args.include_deferred,
        )
    if not todos:
        print("No todos.")
        return
    for t in todos:
        print(f"{t!r}")


def cmd_tree(args: argparse.Namespace) -> None:
    """Render active Todos nested under the Context tree, tree(1)-style -- thin wrapper
    around `kb context tree --todos` (see render_tree in context_cmd.py), so a
    tag-addressed Todo (e.g. "buy salt" @tavern) prints under every Context in the
    tree that carries that tag, not just once, so it's visible wherever it's
    actually actionable without having to check another location's list.

    Scoped to the current context by default, matching `kb context tree`/`kb todo list` --
    `--all` shows the full tree; `--include-deferred` additionally shows not-yet-due
    deferred Todos (the two are independent, pass both together for the old combined
    behavior)."""
    render_tree(
        args.session,
        entity_models=(Todo,),
        active_kwargs={Todo: {"include_deferred": args.include_deferred}},
        scope_to_current=not args.all,
        context=args.context,
    )


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("todo", aliases=["t"], help="Todo operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show Todo details")
    p_show.add_argument("ids", nargs="+", type=int)
    add_history_arg(p_show)
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a Todo")
    p_add.add_argument("title")
    p_add.add_argument(
        "--effort",
        choices=[e.value for e in WishlistEffort],
        help="grab = quick/batchable, research = needs investigation, project = multi-step",
    )
    p_add.add_argument(
        "--defer-until",
        metavar="WHEN",
        help="Hide from `todo pending`/summary until this time — HH:MM (today, or tomorrow if already past), "
        "'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM'",
    )
    p_add.add_argument("--notes")
    p_add.add_argument("--tag", help="Address by Tag instead of context (mutually exclusive with the global --context)")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Todo")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--title")
    p_update.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_update.add_argument(
        "--defer-until",
        metavar="WHEN",
        help="HH:MM (today, or tomorrow if already past), 'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM'",
    )
    p_update.add_argument("--notes")
    p_update_ctx = p_update.add_mutually_exclusive_group()
    p_update_ctx.add_argument("--context", dest="new_context", metavar="NAME")
    p_update_ctx.add_argument("--tag", dest="new_tag", metavar="NAME")
    p_update.add_argument("--goal", type=int, metavar="GOAL_ID")
    p_update.set_defaults(func=cmd_update)

    p_complete = sub.add_parser("complete", help="Mark Todo(s) done")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)

    p_pending = sub.add_parser("pending", help="List pending Todos, optionally filtered by effort")
    p_pending.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_pending.add_argument("--all", action="store_true", help="Also include deferred Todos not yet due")
    p_pending.set_defaults(func=cmd_pending)

    p_list = sub.add_parser(
        "list", help="List pending Todos scoped to the current context (plus descendants/no-context)"
    )
    p_list.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_list.add_argument("--all", action="store_true", help="Ignore context scoping and show Todos from every context")
    p_list.add_argument("--include-deferred", action="store_true", help="Also include deferred Todos not yet due")
    p_list.set_defaults(func=cmd_list)

    p_tree = sub.add_parser(
        "tree", help="Render pending Todos nested under the Context tree (tag-addressed Todos repeat per match)"
    )
    p_tree.add_argument("--all", action="store_true", help="Show the full tree, not just the current context")
    p_tree.add_argument("--include-deferred", action="store_true", help="Also include deferred Todos not yet due")
    p_tree.set_defaults(func=cmd_tree)

    p_search = sub.add_parser(
        "search",
        help="Search Todos by text (unscoped by default; pass the global "
        "`kb --context NAME todo search ...` to restrict to that context's subtree)",
    )
    p_search.add_argument("query")
    p_search.add_argument("--all", action="store_true", help="Also include done/dropped Todos (excluded by default)")
    p_search.set_defaults(func=cmd_search, model=Todo)
