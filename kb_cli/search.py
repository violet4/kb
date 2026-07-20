"""Shared free-text search across kb entities.

The one search engine behind `kb wishlist search`, `kb goal search`, `kb todo search`,
and the top-level `kb search` -- each of those is a thin call into `search_entities`
with a different set of models, so "what counts as a match" (ilike over title/description/
notes) is defined once here rather than reimplemented per command.
"""

import argparse
from typing import Any, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Collection, Goal, GoalStatus, Instruction, Note, Todo, TodoStatus, Wishlist, WishlistStatus

# Models searchable from the top-level `kb search`, in display order.
ALL_SEARCHABLE: tuple[Any, ...] = (Goal, Todo, Wishlist, Instruction)

_TEXT_COLUMNS = ("title", "description", "notes", "body")

# Statuses that mean "no longer open" -- excluded by default from search results,
# matching the `list --all` convention (todo list --all, goal list --all).
TERMINAL_STATUSES: dict[Any, set[Any]] = {
    Goal: {GoalStatus.COMPLETED, GoalStatus.ABANDONED},
    Todo: {TodoStatus.DONE, TodoStatus.DROPPED},
    Wishlist: {WishlistStatus.ACQUIRED, WishlistStatus.DROPPED},
}


def search_entities(session: Session, models: Sequence[Any], query: str, include_done: bool = False) -> list[Any]:
    """Case-insensitive substring search over each model's title/description/notes columns.

    Excludes terminal-status rows (done/abandoned/dropped/acquired) by default;
    pass include_done=True to opt back in.
    """
    pattern = f"%{query}%"
    results: list[Any] = []
    for model in models:
        columns = [getattr(model, col) for col in _TEXT_COLUMNS if hasattr(model, col)]
        rows = session.scalars(select(model).where(or_(*(c.ilike(pattern) for c in columns)))).all()
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
    _print_results(search_entities(args.session, (args.model,), args.query, include_done=args.all))


def cmd_search_all(args: argparse.Namespace) -> None:
    include_done = args.all
    _print_results(search_entities(args.session, ALL_SEARCHABLE, args.query, include_done=include_done))

    notes = Note.search(args.session, args.query)
    if notes:
        print("=== Notes (semantic) ===")
        for note, dist in notes:
            tags = f" #{note.tags}" if note.tags else ""
            print(f"#{note.id} {note.title!r} [{note.collection.value}]{tags} (dist={dist:.3f})")

    todos = Todo.search(args.session, args.query)
    if not include_done:
        todos = [(t, d) for t, d in todos if t.status not in TERMINAL_STATUSES[Todo]]
    if todos:
        print("=== Todos (semantic) ===")
        for todo, dist in todos:
            print(f"#{todo.id} {todo.title!r} [{todo.status.value}] (dist={dist:.3f})")

    goals = Goal.search(args.session, args.query)
    if not include_done:
        goals = [(g, d) for g, d in goals if g.status not in TERMINAL_STATUSES[Goal]]
    if goals:
        print("=== Goals (semantic) ===")
        for goal, dist in goals:
            print(f"#{goal.id} {goal.title!r} [{goal.status.value}] (dist={dist:.3f})")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "search", help="Search Goals, Todos, and Wishlist items by text, plus Notes by semantic similarity"
    )
    parser.add_argument("query")
    parser.add_argument(
        "--all", action="store_true", help="Also include done/abandoned/dropped/acquired items (excluded by default)"
    )
    parser.set_defaults(func=cmd_search_all)
