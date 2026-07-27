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
    HasEmbedding,
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


def _fmt_result(item: Any, dist: float, truncate: bool = True) -> str:
    """truncate=False keeps full body text -- used when a single model is being searched
    on its own (e.g. `kb log search`, where the body IS the point) rather than aggregated
    alongside other entity types (the top-level `kb search`, where compactness matters more
    since many different kinds of rows are printed together)."""
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
        when = item.occurred_at.strftime("%Y-%m-%d %H:%M")
        domain = f" [{item.domain}]" if item.domain else ""
        body = item.body if (not truncate or len(item.body) <= 60) else item.body[:60] + "…"
        return f"#{item.id} {when}{domain}: {body} ({label})"
    return f"{item!r} ({label})"


def _semantic_hits(
    model: type[HasEmbedding],
    session: Session,
    query: str,
    limit: int,
    context: Optional[Context],
    vec: bytes,
    include_done: bool,
) -> list[tuple[Any, float]]:
    """One model's semantic pass: fetch, then drop terminal-status rows (done/dropped/
    promoted/...) unless include_done -- the same filter TERMINAL_STATUSES.get(model)
    already expresses for the substring side, applied here too so both passes agree on
    what counts as "no longer open" for models that track status."""
    hits = model.search(session, query, limit=limit, context=context, vec=vec)
    if not include_done:
        terminal = TERMINAL_STATUSES.get(model)
        if terminal is not None:
            hits = [(obj, dist) for obj, dist in hits if obj.status not in terminal]
    return hits


# Models with semantic search (HasEmbedding), searched by the top-level `kb search` and
# by cmd_search_one below. Order matches ALL_SEARCHABLE's display order where applicable.
SEMANTIC_SEARCHABLE: tuple[type[HasEmbedding], ...] = (Note, Todo, Goal, Instruction, Idea, LogEntry)


def _rank_and_print(scored: list[tuple[Any, float]], limit: int, truncate: bool = True) -> None:
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
        print(_fmt_result(item, dist, truncate=truncate))


def cmd_search_one(args: argparse.Namespace) -> None:
    """Generic handler for a single model's `search` subcommand (e.g. `kb idea search`,
    `kb log search`) that has semantic search (HasEmbedding) -- set args.model beforehand.
    Runs the substring pass (skipped for models without title/name/description/notes/body
    columns worth ilike-matching, e.g. LogEntry, which only has body but no separate
    natural-language fields to substring-match beyond what semantic search already covers
    better) plus the semantic pass, ranked and de-duped together the same way the
    top-level `kb search` aggregates across models."""
    model = args.model
    include_done = getattr(args, "all", False)
    context = args.context if args.context_explicit else None

    scored: list[tuple[Any, float]] = []
    if getattr(args, "has_substring", True):
        substring_hits = search_entities(args.session, (model,), args.query, include_done=include_done, context=context)
        scored.extend((item, _SUBSTRING_DIST) for item in substring_hits)

    from embed import embed
    import struct

    raw = embed(args.query)
    vec = struct.pack(f"{len(raw)}f", *raw)
    scored.extend(_semantic_hits(model, args.session, args.query, args.limit, context, vec, include_done))

    # A single-model search view (e.g. `kb log search`) can afford to show full text --
    # only the multi-model aggregate (`kb search`) needs the 60-char LogEntry truncation.
    _rank_and_print(scored, args.limit, truncate=False)


def cmd_search_all(args: argparse.Namespace) -> None:
    include_done = args.all
    context = args.context if args.context_explicit else None
    limit = args.limit

    substring_hits = search_entities(
        args.session, ALL_SEARCHABLE, args.query, include_done=include_done, context=context
    )
    scored: list[tuple[Any, float]] = [(item, _SUBSTRING_DIST) for item in substring_hits]

    # Embed the query once and reuse the vector across every semantic search below,
    # rather than each one calling embed() independently for identical text.
    import struct

    from embed import embed

    raw = embed(args.query)
    vec = struct.pack(f"{len(raw)}f", *raw)

    for model in SEMANTIC_SEARCHABLE:
        scored.extend(_semantic_hits(model, args.session, args.query, limit, context, vec, include_done))

    _rank_and_print(scored, limit)


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
