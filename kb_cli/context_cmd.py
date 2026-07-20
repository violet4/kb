"""Context operations."""

import argparse
import sys
from typing import Any, Optional

from sqlalchemy import func, select

from context import switch_current
from models import (
    Context,
    CurrentContext,
    Daily,
    Goal,
    Idea,
    Item,
    LogEntry,
    Reference,
    Tag,
    Timer,
    Todo,
    WorkingMemory,
    Wishlist,
)

from kb_cli._util import get_by_name

# Every model that can be pinned to a context, in the order counts should print.
CONTEXT_LINKED_MODELS = (Goal, Todo, Daily, Item, Reference, WorkingMemory, LogEntry, Wishlist, Idea, Timer)

# LogEntry is a timestamped fact, not a status-bearing entity -- worth counting but not worth listing.
# Idea gets its own --ideas flag instead of clogging up the default listing.
# One flag's model tuple per --<flag> in `context tree`; --entities is the union of all of these.
ENTITY_FLAG_MODELS: dict[str, tuple[Any, ...]] = {
    "goals": (Goal,),
    "todos": (Todo,),
    "dailies": (Daily,),
    "items": (Item,),
}
ALL_ENTITY_MODELS = tuple(m for m in CONTEXT_LINKED_MODELS if m not in (LogEntry, Idea))


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
    context = switch_current(args.session, args.name)
    args.session.commit()
    print(f"Current context: {context.name!r}")


def cmd_clear(args: argparse.Namespace) -> None:
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


def _matches_node(model: Any, node: Context) -> Any:
    """Match expression for one model against a single Context -- context_id.in_([node.id])
    plus tag_id fan-out for models that support it (see HasContextOrTag.matches_contexts).
    Models without tag_id (Item, LogEntry, ...) fall back to a plain context_id match."""
    if hasattr(model, "matches_contexts"):
        return model.matches_contexts([node])
    return model.context_id == node.id


def _content_counts(session: Any, node: Context) -> str:
    """' (Todo: 2, Daily: 1)'-style summary of everything linked to one context, empty string if nothing.

    Counts tag-addressed rows too, for any tag this context carries -- see _content_items.
    """
    parts = []
    for model in CONTEXT_LINKED_MODELS:
        count = session.scalar(select(func.count()).select_from(model).where(_matches_node(model, node)))
        if count:
            parts.append(f"{model.__name__}: {count}")
    return f" ({', '.join(parts)})" if parts else ""


def _content_items(
    session: Any,
    node: Context,
    models: tuple[Any, ...],
    active_kwargs: Optional[dict[Any, dict[str, Any]]] = None,
) -> list[Any]:
    """Every row linked to one context that its own entity considers active right now, across
    the given models -- reuses each model's own __repr__.

    Delegates to each model's own .active(contexts=[node]) (Goal/Todo/Daily/Idea/Timer -- every
    HasContextOrTag model, keyed off matches_contexts rather than active() itself since Wishlist
    also defines .active() but with an unrelated, context-free signature) rather than re-deriving
    "what counts as active" here -- that's the one place status/defer_until/etc. filtering is
    owned, so kb todo tree / kb goal tree / kb context tree --todos can never drift out of sync
    with each other or with `kb todo pending`. Models with no matches_contexts (Item, Reference,
    LogEntry, WorkingMemory, Wishlist) fall back to a plain context/tag match, since they have no
    separate notion of "active" beyond being linked here at all.

    active_kwargs lets a caller pass extra per-model .active() kwargs (e.g. Todo's
    include_deferred=True for `kb todo tree --all`) without this function needing to know
    what any particular model's extra flags mean.
    """
    active_kwargs = active_kwargs or {}
    items: list[Any] = []
    for model in models:
        if hasattr(model, "matches_contexts"):
            items.extend(model.active(session, contexts=[node], **active_kwargs.get(model, {})))
        else:
            items.extend(session.scalars(select(model).where(_matches_node(model, node))).all())
    return items


def _content_ideas(session: Any, node: Context) -> list[Any]:
    """Every Idea linked to one context, including tag-addressed Ideas for tags this context carries."""
    matches = Idea.matches_contexts([node])
    return list(session.scalars(select(Idea).where(matches)).all())


def render_tree(
    session: Any,
    entity_models: tuple[Any, ...] = (),
    show_ideas: bool = False,
    root_name: Optional[str] = None,
    scope_to_current: bool = False,
    active_kwargs: Optional[dict[Any, dict[str, Any]]] = None,
    context: Optional[Context] = None,
) -> None:
    """Render the real parent_id Context tree, tree(1)-style, with each entry an entity linked
    to that Context (directly or via a shared Tag -- see _content_items).

    The one tree-rendering engine behind `kb context tree [--goals|--todos|--dailies|...]`,
    `kb todo tree`, `kb goal tree`, and friends -- each of those is a thin call into this with a
    different `entity_models`, so "what counts as active/visible here" is defined once (in each
    model's own .active(), via _content_items) rather than redefined per command.

    `context` is the resolved scope (args.context -- honors a `--context` override, falling back
    to the persisted current context via resolve_context) used for scope_to_current's tree root.
    It's deliberately separate from the persisted CurrentContext used for the `(current)` marker
    below -- an override changes what's rendered, not what's remembered as "current" for later
    commands, so the marker still reflects the real persisted context even under an override.
    """
    contexts = session.scalars(select(Context)).all()
    if not contexts:
        print("No contexts yet.")
        return
    persisted_current = CurrentContext.get(session)
    scope_root = context if context is not None else persisted_current
    show_counts = bool(entity_models) or show_ideas

    children: dict[Any, list[Context]] = {}
    for c in contexts:
        children.setdefault(c.parent_id, []).append(c)
    for kids in children.values():
        kids.sort(key=lambda c: c.name)

    def render(node: Context, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        marker = " (current)" if persisted_current and persisted_current.id == node.id else ""
        tag_str = f" [{', '.join(t.name for t in node.tags)}]" if node.tags else ""
        counts_str = _content_counts(session, node) if show_counts else ""
        print(f"{prefix}{branch}{node.name} #{node.id}{tag_str}{marker}{counts_str}")
        extension = "    " if is_last else "│   "
        kids = children.get(node.id, [])
        items = _content_items(session, node, entity_models, active_kwargs) if entity_models else []
        ideas = _content_ideas(session, node) if show_ideas else []
        entries = items + ideas
        child_prefix = prefix + extension
        for i, item in enumerate(entries):
            item_is_last = (i == len(entries) - 1) and not kids
            item_branch = "└── " if item_is_last else "├── "
            print(f"{child_prefix}{item_branch}{item!r}")
        for i, kid in enumerate(kids):
            render(kid, child_prefix, i == len(kids) - 1)

    if root_name:
        node = get_by_name(session, Context, root_name)
        render(node, "", True)
        return

    if scope_to_current:
        print(f"context: {scope_root.name}" if scope_root else "context: none", file=sys.stderr)
        if scope_root:
            render(scope_root, "", True)
            print("(scoped to current context -- pass --all to see the full tree)")
            return

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)


def cmd_tree(args: argparse.Namespace) -> None:
    """Render the real parent_id tree, tree(1)-style."""
    want_goals = args.goals or args.gtd
    want_todos = args.todos or args.gtd
    want_dailies = args.dailies or args.gtd
    if args.entities:
        entity_models = ALL_ENTITY_MODELS
    else:
        entity_models = (
            (ENTITY_FLAG_MODELS["goals"] if want_goals else ())
            + (ENTITY_FLAG_MODELS["todos"] if want_todos else ())
            + (ENTITY_FLAG_MODELS["dailies"] if want_dailies else ())
            + (ENTITY_FLAG_MODELS["items"] if args.items else ())
        )
    render_tree(
        args.session,
        entity_models=entity_models,
        show_ideas=args.ideas,
        root_name=args.name,
        scope_to_current=not args.all,
        context=args.context,
    )


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

    p_switch = sub.add_parser("switch", help="Change the active context (persists, affects every shell)")
    p_switch.add_argument("name")
    p_switch.set_defaults(func=cmd_switch)

    p_clear = sub.add_parser("clear", help="Clear the active context (persists, affects every shell)")
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
        help="Show the full context tree instead of scoping to the current context",
    )
    p_tree.add_argument(
        "--counts",
        action="store_true",
        help="Annotate each context with counts of everything linked to it (Goals, Todos, Dailies, ...)",
    )
    p_tree.add_argument(
        "--goals",
        action="store_true",
        help="List active (non-terminal) Goals linked to each context (implies --counts)",
    )
    p_tree.add_argument(
        "--todos",
        action="store_true",
        help="List active (non-terminal) Todos linked to each context (implies --counts)",
    )
    p_tree.add_argument(
        "--dailies",
        action="store_true",
        help="List Dailies linked to each context (implies --counts)",
    )
    p_tree.add_argument(
        "--gtd",
        action="store_true",
        help="Shorthand for --goals --todos --dailies",
    )
    p_tree.add_argument(
        "--items",
        action="store_true",
        help="List Items linked to each context (implies --counts)",
    )
    p_tree.add_argument(
        "--entities",
        action="store_true",
        help="List every active (non-terminal) entity of every kind linked to each context, i.e. --gtd --items plus Reference/WorkingMemory/Wishlist/Timer (implies --counts)",
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
