"""Shared free-text search across kb entities.

The one search engine behind `kb wishlist search`, `kb goal search`, `kb todo search`,
and the top-level `kb search` -- each of those is a thin call into `search_entities`
with a different set of models, so "what counts as a match" (ilike over title/name/
description/notes) is defined once here rather than reimplemented per command.
"""

import argparse
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import (
    ArchivedLink,
    Collection,
    Context,
    Daily,
    Event,
    Goal,
    GoalStatus,
    HasContextOrTag,
    HasEmbedding,
    Idea,
    IdeaStatus,
    Instruction,
    Item,
    LogEntry,
    Note,
    Purchase,
    Todo,
    TodoStatus,
    Vendor,
    Wishlist,
    WishlistStatus,
)

from kb_cli._util import scope_to_context

# Models searchable from the top-level `kb search`, in display order.
ALL_SEARCHABLE: tuple[Any, ...] = (
    Goal,
    Todo,
    Wishlist,
    Instruction,
    Idea,
    Context,
    Daily,
    Event,
    ArchivedLink,
    Vendor,
    Item,
)

_TEXT_COLUMNS = ("title", "name", "description", "notes", "body")

# Statuses that mean "no longer open" -- excluded by default from search results,
# matching the `list --all` convention (todo list --all, goal list --all).
TERMINAL_STATUSES: dict[Any, set[Any]] = {
    Goal: {GoalStatus.COMPLETED, GoalStatus.ABANDONED},
    Todo: {TodoStatus.DONE, TodoStatus.DROPPED},
    Wishlist: {WishlistStatus.ACQUIRED, WishlistStatus.DROPPED},
    Idea: {IdeaStatus.PROMOTED, IdeaStatus.DROPPED},
}


def parse_since(value: str) -> datetime:
    """Parse a `--since` CLI value into a UTC-aware datetime. Accepts a bare date
    (`2026-07-28`, midnight UTC) or a full ISO timestamp (`2026-07-28T18:00:00`).
    A naive result is assumed UTC, matching every timestamp column in this project
    (see `_now()` in base.py -- everything is written in UTC)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _date_column(model: Any) -> Any:
    """The column expression (class-level) that answers "when did this happen" for a
    model -- `occurred_at` for LogEntry (a fact about the world at a point in time,
    which may differ from when the row was inserted), `created_at` for everything else.
    Used to build a SQL WHERE clause; see `_row_date` for the matching instance-level read."""
    return getattr(model, "occurred_at", None) if hasattr(model, "occurred_at") else model.created_at


def _row_date(obj: Any) -> datetime:
    """Instance-level counterpart to `_date_column` -- the actual timestamp value on a
    fetched row, read the same way (`occurred_at` if present, else `created_at`).
    SQLite drops tzinfo from DateTime(timezone=True) columns on readback even though
    every writer (`_now()`, see base.py) always stores UTC -- reattach it here before
    comparing against `since` (which is itself tz-aware, from parse_since)."""
    raw = obj.occurred_at if hasattr(obj, "occurred_at") else obj.created_at
    assert isinstance(raw, datetime)
    return raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw


def search_entities(
    session: Session,
    models: Sequence[Any],
    query: str,
    include_done: bool = False,
    context: Optional[Context] = None,
    since: Optional[datetime] = None,
    **filters: Any,
) -> list[Any]:
    """Case-insensitive substring search over each model's title/description/notes columns.

    Excludes terminal-status rows (done/abandoned/dropped/acquired) by default;
    pass include_done=True to opt back in. Unscoped by default (search's whole point is
    finding things regardless of location) -- pass context to additionally restrict
    HasContextOrTag models (Goal/Todo/Idea/Instruction/...) to that context's subtree
    (plus no-context rows), matching `list`/`tree`'s scoping. Models without a context/tag
    (Wishlist, Context itself) are unaffected by this filter.

    `since`, when given, additionally restricts to rows at or after that timestamp,
    compared against `occurred_at` for LogEntry (a fact about the world, not row-insert
    time) or `created_at` for everything else.

    `filters` are extra `column=value` equality clauses (e.g. domain="claude-behavior"),
    applied only to models that actually have the named column -- mirrors HasEmbedding.search's
    own `**filters` so both search passes accept the same filter shape."""
    pattern = f"%{query}%"
    in_scope = scope_to_context(session, context) if context is not None else None
    results: list[Any] = []
    for model in models:
        columns = [getattr(model, col) for col in _TEXT_COLUMNS if hasattr(model, col)]
        q = select(model).where(or_(*(c.ilike(pattern) for c in columns)))
        if in_scope is not None and issubclass(model, HasContextOrTag):
            match = model.matches_contexts(in_scope)
            q = q.where(match | (model.context_id.is_(None) & model.tag_id.is_(None)))
        if since is not None:
            q = q.where(_date_column(model) >= since)
        for col, value in filters.items():
            if hasattr(model, col):
                q = q.where(getattr(model, col) == value)
        rows = session.scalars(q).all()
        if not include_done:
            terminal = TERMINAL_STATUSES.get(model)
            if terminal is not None:
                rows = [r for r in rows if r.status not in terminal]
            elif model is Daily:
                rows = [r for r in rows if r.is_active]
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
        return f"#{item.id} {item.title!r} [Note/{item.collection.value}]{tags}{item.age_marker()} ({label})"
    if isinstance(item, Todo):
        return f"#{item.id} {item.title!r} [Todo/{item.status.value}]{item.age_marker()} ({label})"
    if isinstance(item, Goal):
        return f"#{item.id} {item.title!r} [Goal/{item.status.value}]{item.age_marker()} ({label})"
    if isinstance(item, Instruction):
        trigger = f" trigger={item.trigger!r}" if item.trigger else ""
        return f"#{item.id} {item.title!r} [Instruction]{trigger}{item.age_marker()} ({label})"
    if isinstance(item, Idea):
        return f"#{item.id} {item.title!r} [Idea/{item.status.value}]{item.age_marker()} ({label})"
    if isinstance(item, Daily):
        return f"#{item.id} {item.description!r} [Daily] ({label})"
    if isinstance(item, Event):
        occ = item.next_occurrence()
        when = "past" if occ is None else (occ.date().isoformat() if item.is_all_day else occ.isoformat())
        return f"#{item.id} {item.title!r} [Event/{when}]{item.age_marker()} ({label})"
    if isinstance(item, LogEntry):
        when = item.occurred_at.strftime("%Y-%m-%d %H:%M")
        domain = f" [{item.domain}]" if item.domain else ""
        body = item.body if (not truncate or len(item.body) <= 60) else item.body[:60] + "…"
        return f"#{item.id} {when}{domain}: {body} ({label})"
    if isinstance(item, ArchivedLink):
        content = item.content_status.value if item.content_status.value != "not_attempted" else "title+reason only"
        return f"AB{item.id} {item.title!r} [{content}] ({label})"
    if isinstance(item, Vendor):
        return f"#{item.id} {item.name!r} [Vendor/{item.domain}]{item.age_marker()} ({label})"
    if isinstance(item, Item):
        return f"#{item.id} {item.name!r} [Item/{item.game}]{item.age_marker()} ({label})"
    if isinstance(item, Purchase):
        name = item.vendor_item.item.name if item.vendor_item and item.vendor_item.item else "?"
        return f"#{item.id} {item.quantity}x {name!r} [Purchase] ({label})"
    return f"{item!r} ({label})"


def _semantic_hits(
    model: type[HasEmbedding],
    session: Session,
    query: str,
    limit: int,
    context: Optional[Context],
    vec: bytes,
    include_done: bool,
    since: Optional[datetime] = None,
    **filters: Any,
) -> list[tuple[Any, float]]:
    """One model's semantic pass: fetch, then drop terminal-status rows (done/dropped/
    promoted/...) unless include_done -- the same filter TERMINAL_STATUSES.get(model)
    already expresses for the substring side, applied here too so both passes agree on
    what counts as "no longer open" for models that track status. `since` is likewise a
    post-fetch filter (model.search's SQL only supports equality filters), dropping rows
    older than the cutoff -- fine at this scale since semantic fetch_limit is already
    capped at 200. `filters` are extra column=value equality clauses forwarded straight
    to HasEmbedding.search (e.g. domain="claude-behavior" to scope to flagged entries)."""
    hits = model.search(session, query, limit=limit, context=context, vec=vec, **filters)
    if not include_done:
        terminal = TERMINAL_STATUSES.get(model)
        if terminal is not None:
            hits = [(obj, dist) for obj, dist in hits if obj.status not in terminal]
        elif model is Daily:
            hits = [(obj, dist) for obj, dist in hits if obj.is_active]
    if since is not None:
        hits = [(obj, dist) for obj, dist in hits if _row_date(obj) >= since]
    return hits


# Models with semantic search (HasEmbedding), searched by the top-level `kb search` and
# by cmd_search_one below. Order matches ALL_SEARCHABLE's display order where applicable.
SEMANTIC_SEARCHABLE: tuple[type[HasEmbedding], ...] = (
    Note,
    Todo,
    Goal,
    Instruction,
    Idea,
    Daily,
    Event,
    LogEntry,
    ArchivedLink,
    Vendor,
    Item,
    Purchase,
)


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
    since = parse_since(args.since) if getattr(args, "since", None) else None
    filters: dict[str, Any] = {"domain": "claude-behavior"} if getattr(args, "flags_only", False) else {}

    scored: list[tuple[Any, float]] = []
    if getattr(args, "has_substring", True):
        substring_hits = search_entities(
            args.session, (model,), args.query, include_done=include_done, context=context, since=since, **filters
        )
        scored.extend((item, _SUBSTRING_DIST) for item in substring_hits)

    from embed import embed
    import struct

    raw = embed(args.query)
    vec = struct.pack(f"{len(raw)}f", *raw)
    scored.extend(
        _semantic_hits(model, args.session, args.query, args.limit, context, vec, include_done, since, **filters)
    )

    # A single-model search view (e.g. `kb log search`) can afford to show full text --
    # only the multi-model aggregate (`kb search`) needs the 60-char LogEntry truncation.
    _rank_and_print(scored, args.limit, truncate=False)


def _run_one_search(args: argparse.Namespace, query: str) -> None:
    include_done = args.all
    context = args.context if args.context_explicit else None
    limit = args.limit
    since = parse_since(args.since) if getattr(args, "since", None) else None

    substring_hits = search_entities(
        args.session, ALL_SEARCHABLE, query, include_done=include_done, context=context, since=since
    )
    scored: list[tuple[Any, float]] = [(item, _SUBSTRING_DIST) for item in substring_hits]

    # Embed the query once and reuse the vector across every semantic search below,
    # rather than each one calling embed() independently for identical text.
    import struct

    from embed import embed

    raw = embed(query)
    vec = struct.pack(f"{len(raw)}f", *raw)

    for model in SEMANTIC_SEARCHABLE:
        scored.extend(_semantic_hits(model, args.session, query, limit, context, vec, include_done, since))

    _rank_and_print(scored, limit)


def cmd_search_all(args: argparse.Namespace) -> None:
    queries: list[str] = args.query
    for i, query in enumerate(queries):
        if len(queries) > 1:
            if i:
                print()
            print(f"-- {query} --")
        _run_one_search(args, query)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "search",
        help="Search Goals, Todos, Wishlist items, Instructions, Ideas, Contexts, and Dailies by substring, plus "
        "Notes, Todos, Goals, Instructions, Ideas, and LogEntries by semantic similarity -- all ranked "
        "together by score (unscoped by default; pass the global `kb --context NAME search ...` to "
        "restrict context/tag-addressable results to that context's subtree)",
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="One or more search queries (quote each one separately, e.g. `kb search 'first topic' 'second topic'`) -- "
        "results for each are printed under their own header",
    )
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
    parser.add_argument(
        "--since",
        help="Only include rows at or after this date/timestamp (e.g. `2026-07-28` or "
        "`2026-07-28T18:00:00`; a bare date means midnight UTC). Compared against `occurred_at` "
        "for LogEntry, `created_at` for everything else.",
    )
    parser.set_defaults(func=cmd_search_all)
