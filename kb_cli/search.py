"""Shared free-text search across kb entities.

The one search engine behind `kb wishlist search`, `kb goal search`, `kb todo search`,
and the top-level `kb search` -- each of those is a thin call into `search_entities`
with a different set of models, so "what counts as a match" (ilike over title/name/
description/notes) is defined once here rather than reimplemented per command.
"""

import argparse
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import (
    Collection,
    Context,
    Goal,
    GoalStatus,
    HasContextOrTag,
    Idea,
    IdeaStatus,
    Instruction,
    LogEntry,
    Note,
    Todo,
    TodoStatus,
    Wishlist,
    WishlistStatus,
)

from kb_cli._util import scope_to_context

# Models searchable from the top-level `kb search`, in display order.
ALL_SEARCHABLE: tuple[Any, ...] = (Goal, Todo, Wishlist, Instruction, Idea, Context)

_TEXT_COLUMNS = ("title", "name", "description", "notes", "body")

# Statuses that mean "no longer open" -- excluded by default from search results,
# matching the `list --all` convention (todo list --all, goal list --all).
TERMINAL_STATUSES: dict[Any, set[Any]] = {
    Goal: {GoalStatus.COMPLETED, GoalStatus.ABANDONED},
    Todo: {TodoStatus.DONE, TodoStatus.DROPPED},
    Wishlist: {WishlistStatus.ACQUIRED, WishlistStatus.DROPPED},
    Idea: {IdeaStatus.PROMOTED, IdeaStatus.DROPPED},
}


def search_entities(
    session: Session,
    models: Sequence[Any],
    query: str,
    include_done: bool = False,
    context: Optional[Context] = None,
) -> list[Any]:
    """Case-insensitive substring search over each model's title/description/notes columns.

    Excludes terminal-status rows (done/abandoned/dropped/acquired) by default;
    pass include_done=True to opt back in. Unscoped by default (search's whole point is
    finding things regardless of location) -- pass context to additionally restrict
    HasContextOrTag models (Goal/Todo/Idea/Instruction/...) to that context's subtree
    (plus no-context rows), matching `list`/`tree`'s scoping. Models without a context/tag
    (Wishlist, Context itself) are unaffected by this filter."""
    pattern = f"%{query}%"
    in_scope = scope_to_context(session, context) if context is not None else None
    results: list[Any] = []
    for model in models:
        columns = [getattr(model, col) for col in _TEXT_COLUMNS if hasattr(model, col)]
        q = select(model).where(or_(*(c.ilike(pattern) for c in columns)))
        if in_scope is not None and issubclass(model, HasContextOrTag):
            match = model.matches_contexts(in_scope)
            q = q.where(match | (model.context_id.is_(None) & model.tag_id.is_(None)))
        rows = session.scalars(q).all()
        if not include_done:
            terminal = TERMINAL_STATUSES.get(model)
            if terminal is not None:
                rows = [r for r in rows if r.status not in terminal]
        results.extend(rows)
    return results


def _print_results(items: list[Any]) -> None:
    if not items:
        print("No matches.")
        return
    for item in items:
        print(repr(item))


def cmd_search(args: argparse.Namespace) -> None:
    """Generic handler for a single-model `search` subcommand; set args.model beforehand."""
    context = args.context if args.context_explicit else None
    _print_results(search_entities(args.session, (args.model,), args.query, include_done=args.all, context=context))


# Substring matches are exact hits, not distance-scored -- rank them ahead of every
# semantic result by giving them this sentinel distance rather than a real cosine distance.
_SUBSTRING_DIST = -1.0


def _fmt_result(item: Any, dist: float) -> str:
    label = "substring" if dist == _SUBSTRING_DIST else f"dist={dist:.3f}"
    if isinstance(item, Note):
        tags = f" #{item.tags}" if item.tags else ""
        return f"#{item.id} {item.title!r} [Note/{item.collection.value}]{tags} ({label})"
    if isinstance(item, Todo):
        return f"#{item.id} {item.title!r} [Todo/{item.status.value}] ({label})"
    if isinstance(item, Goal):
        return f"#{item.id} {item.title!r} [Goal/{item.status.value}] ({label})"
    if isinstance(item, Instruction):
        trigger = f" trigger={item.trigger!r}" if item.trigger else ""
        return f"#{item.id} {item.title!r} [Instruction]{trigger} ({label})"
    if isinstance(item, Idea):
        return f"#{item.id} {item.title!r} [Idea/{item.status.value}] ({label})"
    if isinstance(item, LogEntry):
        when = item.occurred_at.strftime("%Y-%m-%d")
        body = item.body if len(item.body) <= 60 else item.body[:60] + "…"
        return f"#{item.id} [LogEntry {when}] {body!r} ({label})"
    return f"{item!r} ({label})"


def cmd_search_all(args: argparse.Namespace) -> None:
    include_done = args.all
    context = args.context if args.context_explicit else None
    limit = args.limit

    substring_hits = search_entities(
        args.session, ALL_SEARCHABLE, args.query, include_done=include_done, context=context
    )
    scored: list[tuple[Any, float]] = [(item, _SUBSTRING_DIST) for item in substring_hits]

    # Embed the query once and reuse the vector across all three semantic searches below,
    # rather than each one calling embed() independently for identical text.
    import struct

    from embed import embed

    raw = embed(args.query)
    vec = struct.pack(f"{len(raw)}f", *raw)

    notes = Note.search(args.session, args.query, limit=limit, vec=vec)
    scored.extend(notes)

    todos = Todo.search(args.session, args.query, limit=limit, context=context, vec=vec)
    if not include_done:
        todos = [(t, d) for t, d in todos if t.status not in TERMINAL_STATUSES[Todo]]
    scored.extend(todos)

    goals = Goal.search(args.session, args.query, limit=limit, context=context, vec=vec)
    if not include_done:
        goals = [(g, d) for g, d in goals if g.status not in TERMINAL_STATUSES[Goal]]
    scored.extend(goals)

    instructions = Instruction.search(args.session, args.query, limit=limit, context=context, vec=vec)
    scored.extend(instructions)

    ideas = Idea.search(args.session, args.query, limit=limit, context=context, vec=vec)
    if not include_done:
        ideas = [(i, d) for i, d in ideas if i.status not in TERMINAL_STATUSES[Idea]]
    scored.extend(ideas)

    log_entries = LogEntry.search(args.session, args.query, limit=limit, context=context, vec=vec)
    scored.extend(log_entries)

    # De-dupe: the same row can surface via both the substring pass and a semantic pass --
    # keep the best (lowest-distance, i.e. substring) scoring of the two.
    best: dict[tuple[type, int], tuple[Any, float]] = {}
    for item, dist in scored:
        key = (type(item), item.id)
        if key not in best or dist < best[key][1]:
            best[key] = (item, dist)

    ranked = sorted(best.values(), key=lambda pair: pair[1])[:limit]

    if not ranked:
        print("No matches.")
        return
    for item, dist in ranked:
        print(_fmt_result(item, dist))


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "search",
        help="Search Goals, Todos, Wishlist items, Instructions, Ideas, and Contexts by substring, plus "
        "Notes, Todos, Goals, Instructions, Ideas, and LogEntries by semantic similarity -- all ranked "
        "together by score (unscoped by default; pass the global `kb --context NAME search ...` to "
        "restrict context/tag-addressable results to that context's subtree)",
    )
    parser.add_argument("query")
    parser.add_argument(
        "--all", action="store_true", help="Also include done/abandoned/dropped/acquired items (excluded by default)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max results across all entities combined, ranked by score (substring matches rank first, "
        "then semantic matches by ascending distance)",
    )
    parser.set_defaults(func=cmd_search_all)
