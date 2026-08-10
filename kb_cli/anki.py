"""Read/write an Anki collection directly via the anki Python package.

Anki must be closed while this runs (SQLite file lock) -- this does NOT talk to a running
Anki process, unlike AnkiConnect. Requires the optional 'anki' dependency:
uv sync --project ~/kb --extra anki
"""

import argparse
import ast
import code
import sys
import time
from pathlib import Path
from typing import Any, Type

DEFAULT_COLLECTION = Path.home() / ".local/share/Anki2/User 1/collection.anki2"
LOCK_WAIT_TIMEOUT_SECONDS = 60
LOCK_POLL_INTERVAL_SECONDS = 2

NOTETYPE_ALIASES = {
    "reverse": "Basic (and reversed card)",
    "reverse-optional": "Basic (optional reversed card)",
    "type-answer": "Basic (type in the answer)",
    "reverse-type": "Reverse + Type",
}

# Custom note types kb creates itself (not shipped with Anki) -- each entry is
# (name, fields, [(template_name, qfmt, afmt), ...]). `notetype-init` creates any
# that don't already exist yet, idempotently, so a fresh Anki profile can be brought
# up to the same state with one command.
CUSTOM_NOTETYPES = [
    (
        "Reverse + Type",
        ["Front", "Back"],
        [
            ("Card 1", "{{Front}}\n\n{{type:Back}}", "{{Front}}\n\n<hr id=answer>\n\n{{type:Back}}"),
            ("Card 2", "{{Back}}\n\n{{type:Front}}", "{{Back}}\n\n<hr id=answer>\n\n{{type:Front}}"),
        ],
    ),
]


def _require_anki() -> Type[Any]:
    try:
        from anki.collection import Collection

        result: Type[Any] = Collection
        return result
    except ImportError:
        print(
            "kb anki: the 'anki' package is not installed.\n" "Install it with: uv sync --project ~/kb --extra anki",
            file=sys.stderr,
        )
        sys.exit(1)


def _open_collection(path: str) -> Any:
    Collection = _require_anki()
    col_path = Path(path).expanduser()
    if not col_path.exists():
        print(f"kb anki: collection not found at {col_path}", file=sys.stderr)
        sys.exit(1)

    waited = 0
    warned = False
    while True:
        try:
            return Collection(str(col_path))
        except Exception as e:
            if "already open" not in str(e).lower():
                print(f"kb anki: could not open collection ({e})", file=sys.stderr)
                sys.exit(1)
            if waited >= LOCK_WAIT_TIMEOUT_SECONDS:
                print(
                    f"kb anki: collection still locked after {LOCK_WAIT_TIMEOUT_SECONDS}s -- close Anki and try again.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not warned:
                print("kb anki: Anki is still open -- close it to continue. Waiting...", file=sys.stderr)
                warned = True
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
            waited += LOCK_POLL_INTERVAL_SECONDS


def cmd_decks(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        for deck in col.decks.all_names_and_ids():
            count = len(col.find_notes(f'deck:"{deck.name}"'))
            print(f"{deck.name} ({count} notes)")
    finally:
        col.close()


def cmd_notetype_init(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        for name, fields, templates in CUSTOM_NOTETYPES:
            if col.models.by_name(name) is not None:
                print(f"Note type {name!r} already exists, skipping.")
                continue
            m = col.models.new(name)
            for field_name in fields:
                col.models.add_field(m, col.models.new_field(field_name))
            for template_name, qfmt, afmt in templates:
                t = col.models.new_template(template_name)
                t["qfmt"] = qfmt
                t["afmt"] = afmt
                col.models.add_template(m, t)
            col.models.add_dict(m)
            print(f"Created note type {name!r}.")
    finally:
        col.close()


def cmd_deck_add(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        existing = col.decks.by_name(args.name)
        if existing is not None:
            print(f"kb anki: deck {args.name!r} already exists", file=sys.stderr)
            sys.exit(1)
        col.decks.add_normal_deck_with_name(args.name)
        print(f"Created deck {args.name!r}")
    finally:
        col.close()


def cmd_search(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        note_ids = col.find_notes(args.query)
        if not note_ids:
            print("No matching notes.")
            return
        for nid in note_ids:
            note = col.get_note(nid)
            fields = " | ".join(note.values())
            print(f"{nid}: {fields}")
    finally:
        col.close()


def cmd_add(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        deck = col.decks.by_name(args.deck)
        if deck is None:
            deck_id = col.decks.add_normal_deck_with_name(args.deck).id
        else:
            deck_id = deck["id"]
        notetype_name = NOTETYPE_ALIASES.get(args.notetype, args.notetype)
        notetype = col.models.by_name(notetype_name)
        if notetype is None:
            print(f"kb anki: note type {notetype_name!r} not found", file=sys.stderr)
            sys.exit(1)
        note = col.new_note(notetype)
        for field, value in zip(note.keys(), args.fields):
            note[field] = value
        if args.tags:
            note.tags = args.tags.split()
        col.add_note(note, deck_id)
        print(f"Added note {note.id} to deck {args.deck!r}")
    finally:
        col.close()


def cmd_delete(args: argparse.Namespace) -> None:
    col = _open_collection(args.collection)
    try:
        to_delete = []
        for nid in args.ids:
            try:
                note = col.get_note(nid)
            except Exception:
                print(f"kb anki: note {nid} not found", file=sys.stderr)
                continue
            fields = " | ".join(note.values())
            print(f"Deleting {nid}: {fields}")
            to_delete.append(nid)
        if to_delete:
            col.remove_notes(to_delete)
            print(f"Deleted {len(to_delete)} note(s).")
    finally:
        col.close()


def cmd_run(args: argparse.Namespace) -> None:
    if not args.command and not args.file and not args.interactive:
        print("kb anki run: one of: command, -f/--file, or -i/--interactive is required", file=sys.stderr)
        sys.exit(2)

    command = args.command
    if args.file:
        if args.file == "-":
            command = sys.stdin.read()
        else:
            with open(args.file) as f:
                command = f.read()

    col = _open_collection(args.collection)
    try:
        ns = {"col": col}
        if command:
            tree = ast.parse(command)
            last_expr = None
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                last_expr = ast.Expression(tree.body.pop().value)
            try:
                exec(compile(tree, "<kb anki run>", "exec"), ns)  # noqa: S102
                if last_expr is not None:
                    result = eval(compile(last_expr, "<kb anki run>", "eval"), ns)  # noqa: S307
                    if result is not None:
                        print(repr(result))
            except Exception:
                print("kb anki run: command raised", file=sys.stderr)
                raise
        else:
            banner = "kb anki interactive mode | `col` (the open Collection) is pre-loaded. Anki auto-saves most mutations; col.close() happens on exit."
            code.interact(banner=banner, local=ns, exitmsg="")
    finally:
        col.close()


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("anki", help="Read/write an Anki collection directly (Anki must be closed)")
    parser.add_argument(
        "--collection",
        default=str(DEFAULT_COLLECTION),
        help=f"Path to collection.anki2 (default: {DEFAULT_COLLECTION})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_decks = sub.add_parser("decks", help="List decks and their note counts")
    p_decks.set_defaults(func=cmd_decks)

    p_notetype_init = sub.add_parser(
        "notetype-init", help="Create kb's custom note types (e.g. Reverse + Type) if not already present"
    )
    p_notetype_init.set_defaults(func=cmd_notetype_init)

    p_deck_add = sub.add_parser("deck-add", help="Create a new deck")
    p_deck_add.add_argument("name")
    p_deck_add.set_defaults(func=cmd_deck_add)

    p_search = sub.add_parser("search", help="Search notes (Anki search syntax, e.g. 'deck:Spanish')")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_add = sub.add_parser("add", help="Add a note")
    p_add.add_argument("deck")
    p_add.add_argument("notetype", help="e.g. 'Basic', or an alias: reverse, reverse-optional, type-answer")
    p_add.add_argument("fields", nargs="+", help="Field values in order, e.g. Front Back for a Basic note")
    p_add.add_argument("--tags", help="Space-separated tags")
    p_add.set_defaults(func=cmd_add)

    p_delete = sub.add_parser("delete", help="Delete note(s) by id")
    p_delete.add_argument("ids", nargs="+", type=int)
    p_delete.set_defaults(func=cmd_delete)

    p_run = sub.add_parser(
        "run",
        help="Run a Python expression/script against the open collection (like kb_repl.py, but col instead of sess)",
    )
    p_run.add_argument("command", nargs="?", help="Python expression to execute")
    p_run.add_argument(
        "-f", "--file", help="Read command from a script file instead of the command arg (use '-' for stdin)"
    )
    p_run.add_argument(
        "-i", "--interactive", action="store_true", help="Start an interactive REPL with `col` pre-loaded"
    )
    p_run.set_defaults(func=cmd_run)
