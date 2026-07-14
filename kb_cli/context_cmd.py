"""Context operations."""

import argparse
import sys
from typing import Any

from sqlalchemy import func, select

from context import KB_CONTEXT_ENV_VAR, switch_current
from models import (
    Context,
    CurrentContext,
    Daily,
    Goal,
    GoalStatus,
    Idea,
    Item,
    LogEntry,
    Reference,
    Tag,
    Timer,
    Todo,
    TodoStatus,
    WorkingMemory,
    Wishlist,
)

from kb_cli._util import get_by_name

# Every model that can be pinned to a context, in the order counts should print.
CONTEXT_LINKED_MODELS = (Goal, Todo, Daily, Item, Reference, WorkingMemory, LogEntry, Wishlist, Idea, Timer)

# LogEntry is a timestamped fact, not a status-bearing item -- worth counting but not worth listing in --items.
# Idea gets its own --ideas flag instead of clogging up the default --items listing.
ITEM_LISTED_MODELS = tuple(m for m in CONTEXT_LINKED_MODELS if m not in (LogEntry, Idea))

# Terminal statuses to exclude from --items by default -- only active work should clutter the tree.
_GOAL_TERMINAL = (GoalStatus.COMPLETED, GoalStatus.ABANDONED)
_TODO_TERMINAL = (TodoStatus.DONE, TodoStatus.DROPPED)


def cmd_current(args: argparse.Namespace) -> None:
    context = CurrentContext.get(args.session)
    print(context.name if context else "(none)")


def cmd_add(args: argparse.Namespace) -> None:
    existing = args.session.scalars(select(Context).where(Context.name == args.name)).one_or_none()
    if existing is not None:
        print(f"Context {args.name!r} already exists (#{existing.id})", file=sys.stderr)
        sys.exit(1)
    parent = get_by_name(args.session, Context, args.parent) if args.parent else None
    context = Context(name=args.name, description=args.description, parent=parent)
    args.session.add(context)
    args.session.commit()
    print(context)


def cmd_set_parent(args: argparse.Namespace) -> None:
    context = get_by_name(args.session, Context, args.name)
    parent = get_by_name(args.session, Context, args.parent) if args.parent else None
    context.parent = parent
    args.session.commit()
    print(context)


def cmd_switch(args: argparse.Namespace) -> None:
    if args.local:
        # Print an export line rather than touching the DB, ssh-agent style --
        # eval "$(kb context switch NAME --local)" scopes the switch to this shell only.
        print(f"export {KB_CONTEXT_ENV_VAR}={args.name}")
        return
    context = switch_current(args.session, args.name)
    args.session.commit()
    print(f"Current context: {context.name!r}")


def cmd_clear(args: argparse.Namespace) -> None:
    if args.local:
        print(f"unset {KB_CONTEXT_ENV_VAR}")
        return
    CurrentContext.set(args.session, None)
    args.session.commit()
    print("Current context cleared.")


def cmd_list(args: argparse.Namespace) -> None:
    contexts = args.session.scalars(select(Context).order_by(Context.name)).all()
    if not contexts:
        print("No contexts yet.")
        return
    current = CurrentContext.get(args.session)
    for c in contexts:
        marker = " (current)" if current and current.id == c.id else ""
        print(f"#{c.id} {c.name}{marker}")


def _content_counts(session: Any, context_id: int) -> str:
    """' (Todo: 2, Daily: 1)'-style summary of everything linked to one context, empty string if nothing."""
    parts = []
    for model in CONTEXT_LINKED_MODELS:
        count = session.scalar(select(func.count()).select_from(model).where(model.context_id == context_id))
        if count:
            parts.append(f"{model.__name__}: {count}")
    return f" ({', '.join(parts)})" if parts else ""


def _content_items(session: Any, context_id: int) -> list[Any]:
    """Every non-terminal row linked to one context, across all context-bearing models -- reuses each model's own __repr__."""
    items: list[Any] = []
    for model in ITEM_LISTED_MODELS:
        q = select(model).where(model.context_id == context_id)
        if model is Goal:
            q = q.where(Goal.status.notin_(_GOAL_TERMINAL))
        elif model is Todo:
            q = q.where(Todo.status.notin_(_TODO_TERMINAL))
        items.extend(session.scalars(q).all())
    return items


def _content_ideas(session: Any, context_id: int) -> list[Any]:
    """Every Idea linked to one context."""
    return list(session.scalars(select(Idea).where(Idea.context_id == context_id)).all())


def cmd_tree(args: argparse.Namespace) -> None:
    """Render the real parent_id tree, tree(1)-style."""
    contexts = args.session.scalars(select(Context)).all()
    if not contexts:
        print("No contexts yet.")
        return
    current = CurrentContext.get(args.session)
    show_counts = args.counts or args.items or args.ideas
    show_items = args.items
    show_ideas = args.ideas

    children: dict[Any, list[Context]] = {}
    for c in contexts:
        children.setdefault(c.parent_id, []).append(c)
    for kids in children.values():
        kids.sort(key=lambda c: c.name)

    def render(node: Context, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        marker = " (current)" if current and current.id == node.id else ""
        tag_str = f" [{', '.join(t.name for t in node.tags)}]" if node.tags else ""
        counts_str = _content_counts(args.session, node.id) if show_counts else ""
        print(f"{prefix}{branch}{node.name} #{node.id}{tag_str}{marker}{counts_str}")
        extension = "    " if is_last else "│   "
        kids = children.get(node.id, [])
        items = _content_items(args.session, node.id) if show_items else []
        ideas = _content_ideas(args.session, node.id) if show_ideas else []
        entries = items + ideas
        child_prefix = prefix + extension
        for i, item in enumerate(entries):
            item_is_last = (i == len(entries) - 1) and not kids
            item_branch = "└── " if item_is_last else "├── "
            print(f"{child_prefix}{item_branch}{item!r}")
        for i, kid in enumerate(kids):
            render(kid, child_prefix, i == len(kids) - 1)

    if args.name:
        node = get_by_name(args.session, Context, args.name)
        render(node, "", True)
        return

    if not args.all and current:
        render(current, "", True)
        print("(scoped to current context -- pass --all to see the full tree)")
        return

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)


def cmd_tag(args: argparse.Namespace) -> None:
    context = get_by_name(args.session, Context, args.name)
    for tag_name in args.tags:
        tag = args.session.scalars(select(Tag).where(Tag.name == tag_name)).one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            args.session.add(tag)
            args.session.flush()
        if tag not in context.tags:
            context.tags.append(tag)
    args.session.commit()
    print(context)


def cmd_untag(args: argparse.Namespace) -> None:
    context = get_by_name(args.session, Context, args.name)
    for tag_name in args.tags:
        tag = get_by_name(args.session, Tag, tag_name)
        if tag in context.tags:
            context.tags.remove(tag)
    args.session.commit()
    print(context)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("context", aliases=["c"], help="Context operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_current = sub.add_parser("current", help="Show the active context")
    p_current.set_defaults(func=cmd_current)

    p_add = sub.add_parser("add", help="Create a new context, optionally under a parent context")
    p_add.add_argument("name")
    p_add.add_argument("--parent", help="Parent context name (must already exist)")
    p_add.add_argument("--description")
    p_add.set_defaults(func=cmd_add)

    p_set_parent = sub.add_parser("set-parent", help="Change (or clear) a context's parent")
    p_set_parent.add_argument("name")
    p_set_parent.add_argument("parent", nargs="?", help="Omit to clear the parent")
    p_set_parent.set_defaults(func=cmd_set_parent)

    p_switch = sub.add_parser("switch", help="Change the active context")
    p_switch.add_argument("name")
    p_switch.add_argument(
        "--local",
        action="store_true",
        help=f'Print `export {KB_CONTEXT_ENV_VAR}=NAME` instead of persisting -- eval "$(kb context switch NAME --local)" to scope the switch to this shell only',
    )
    p_switch.set_defaults(func=cmd_switch)

    p_clear = sub.add_parser("clear", help="Clear the active context")
    p_clear.add_argument(
        "--local",
        action="store_true",
        help=f'Print `unset {KB_CONTEXT_ENV_VAR}` instead -- eval "$(kb context clear --local)" to clear this shell\'s override only',
    )
    p_clear.set_defaults(func=cmd_clear)

    p_list = sub.add_parser("list", help="List all known contexts (flat)")
    p_list.set_defaults(func=cmd_list)

    p_tree = sub.add_parser("tree", help="Render the context tree, scoped to the current context by default")
    p_tree.add_argument(
        "name",
        nargs="?",
        help="Show the subtree rooted at this named context instead of the current context",
    )
    p_tree.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Show the full tree instead of scoping to the current context",
    )
    p_tree.add_argument(
        "--counts",
        action="store_true",
        help="Annotate each context with counts of everything linked to it (Goals, Todos, Dailies, ...)",
    )
    p_tree.add_argument(
        "--items",
        action="store_true",
        help="List every active (non-terminal) item linked to each context (implies --counts)",
    )
    p_tree.add_argument(
        "--ideas",
        action="store_true",
        help="List every Idea linked to each context (implies --counts)",
    )
    p_tree.set_defaults(func=cmd_tree)

    p_tag = sub.add_parser("tag", help="Attach one or more tags to a context (creates tags that don't exist yet)")
    p_tag.add_argument("name")
    p_tag.add_argument("tags", nargs="+")
    p_tag.set_defaults(func=cmd_tag)

    p_untag = sub.add_parser("untag", help="Remove one or more tags from a context")
    p_untag.add_argument("name")
    p_untag.add_argument("tags", nargs="+")
    p_untag.set_defaults(func=cmd_untag)
