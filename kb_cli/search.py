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

from models import Collection, Goal, Instruction, Note, Todo, Wishlist

# Models searchable from the top-level `kb search`, in display order.
ALL_SEARCHABLE: tuple[Any, ...] = (Goal, Todo, Wishlist, Instruction)

_TEXT_COLUMNS = ("title", "description", "notes", "body")


def search_entities(session: Session, models: Sequence[Any], query: str) -> list[Any]:
    """Case-insensitive substring search over each model's title/description/notes columns."""
    pattern = f"%{query}%"
    results: list[Any] = []
    for model in models:
        columns = [getattr(model, col) for col in _TEXT_COLUMNS if hasattr(model, col)]
        results.extend(session.scalars(select(model).where(or_(*(c.ilike(pattern) for c in columns)))).all())
    return results


def _print_results(items: list[Any]) -> None:
    if not items:
        print("No matches.")
        return
    for item in items:
        print(repr(item))


def cmd_search(args: argparse.Namespace) -> None:
    """Generic handler for a single-model `search` subcommand; set args.model beforehand."""
    _print_results(search_entities(args.session, (args.model,), args.query))


def cmd_search_all(args: argparse.Namespace) -> None:
    _print_results(search_entities(args.session, ALL_SEARCHABLE, args.query))

    notes = Note.search(args.session, args.query)
    if notes:
        print("=== Notes (semantic) ===")
        for note, dist in notes:
            tags = f" #{note.tags}" if note.tags else ""
            print(f"#{note.id} {note.title!r} [{note.collection.value}]{tags} (dist={dist:.3f})")

    todos = Todo.search(args.session, args.query)
    if todos:
        print("=== Todos (semantic) ===")
        for todo, dist in todos:
            print(f"#{todo.id} {todo.title!r} [{todo.status.value}] (dist={dist:.3f})")

    goals = Goal.search(args.session, args.query)
    if goals:
        print("=== Goals (semantic) ===")
        for goal, dist in goals:
            print(f"#{goal.id} {goal.title!r} [{goal.status.value}] (dist={dist:.3f})")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "search", help="Search Goals, Todos, and Wishlist items by text, plus Notes by semantic similarity"
    )
    parser.add_argument("query")
    parser.set_defaults(func=cmd_search_all)
