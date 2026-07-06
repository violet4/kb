"""Read/write an Anki collection directly via the anki Python package.

Anki must be closed while this runs (SQLite file lock) -- this does NOT talk to a running
Anki process, unlike AnkiConnect. Requires the optional 'anki' dependency:
uv sync --project ~/kb --extra anki
"""
import sys
import time
from pathlib import Path

DEFAULT_COLLECTION = Path.home() / ".local/share/Anki2/User 1/collection.anki2"
LOCK_WAIT_TIMEOUT_SECONDS = 60
LOCK_POLL_INTERVAL_SECONDS = 2


def _require_anki():
    try:
        from anki.collection import Collection
        return Collection
    except ImportError:
        print(
            "kb anki: the 'anki' package is not installed.\n"
            "Install it with: uv sync --project ~/kb --extra anki",
            file=sys.stderr,
        )
        sys.exit(1)


def _open_collection(path: str):
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
                print(f"kb anki: collection still locked after {LOCK_WAIT_TIMEOUT_SECONDS}s -- close Anki and try again.", file=sys.stderr)
                sys.exit(1)
            if not warned:
                print("kb anki: Anki is still open -- close it to continue. Waiting...", file=sys.stderr)
                warned = True
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
            waited += LOCK_POLL_INTERVAL_SECONDS


def cmd_decks(args):
    col = _open_collection(args.collection)
    try:
        for deck in col.decks.all_names_and_ids():
            count = len(col.find_notes(f'deck:"{deck.name}"'))
            print(f"{deck.name} ({count} notes)")
    finally:
        col.close()


def cmd_deck_add(args):
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


def cmd_search(args):
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


def cmd_add(args):
    col = _open_collection(args.collection)
    try:
        deck = col.decks.by_name(args.deck)
        if deck is None:
            deck_id = col.decks.add_normal_deck_with_name(args.deck).id
        else:
            deck_id = deck["id"]
        notetype = col.models.by_name(args.notetype)
        if notetype is None:
            print(f"kb anki: note type {args.notetype!r} not found", file=sys.stderr)
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


def cmd_delete(args):
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


def add_subparser(subparsers):
    parser = subparsers.add_parser("anki", help="Read/write an Anki collection directly (Anki must be closed)")
    parser.add_argument("--collection", default=str(DEFAULT_COLLECTION), help=f"Path to collection.anki2 (default: {DEFAULT_COLLECTION})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_decks = sub.add_parser("decks", help="List decks and their note counts")
    p_decks.set_defaults(func=cmd_decks)

    p_deck_add = sub.add_parser("deck-add", help="Create a new deck")
    p_deck_add.add_argument("name")
    p_deck_add.set_defaults(func=cmd_deck_add)

    p_search = sub.add_parser("search", help="Search notes (Anki search syntax, e.g. 'deck:Spanish')")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_add = sub.add_parser("add", help="Add a note")
    p_add.add_argument("deck")
    p_add.add_argument("notetype", help="e.g. 'Basic'")
    p_add.add_argument("fields", nargs="+", help="Field values in order, e.g. Front Back for a Basic note")
    p_add.add_argument("--tags", help="Space-separated tags")
    p_add.set_defaults(func=cmd_add)

    p_delete = sub.add_parser("delete", help="Delete note(s) by id")
    p_delete.add_argument("ids", nargs="+", type=int)
    p_delete.set_defaults(func=cmd_delete)
