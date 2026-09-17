"""Note operations."""

import argparse
import sys
from typing import Optional

from sqlalchemy import select

from client import KBClient
from kb_cli._util import (
    apply_purge,
    apply_restore,
    apply_soft_delete,
    apply_text_edit,
    print_links,
    print_timestamps,
    resolve_body_args,
    resolve_text_arg,
)
from kb_cli.search import cmd_search_deprecated
from models import Collection, Note


def cmd_show(args: argparse.Namespace) -> None:
    note = Note.get(args.session, args.id)
    if note is None:
        print(f"Note #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print(f"id: {note.id}")
    print(f"title: {note.title}")
    print(f"collection: {note.collection.value}")
    if note.tags:
        print(f"tags: {note.tags}")
    print_timestamps(note)
    print(f"body: {note.body}")
    print_links(args.session, "Note", note.id)


def _resolve_collection(name: Optional[str]) -> Optional[Collection]:
    """Resolve a --collection argument, warning and falling back to INBOX if unknown."""
    if name is None:
        return None
    try:
        return Collection(name)
    except ValueError:
        print(
            f'Warning: collection "{name}" not found -- placed in inbox instead. '
            "Relocate with `kb notes update --collection`.",
            file=sys.stderr,
        )
        return Collection.INBOX


def cmd_add(args: argparse.Namespace) -> None:
    collection = _resolve_collection(args.collection) or Collection.INBOX
    client = KBClient()
    result = client.note_create(
        title=resolve_text_arg(args.title),
        body=resolve_body_args(args.body, args.body_file),
        collection=collection.value,
        tags=args.tags,
    )
    print(f"Added: {result}")


def cmd_update(args: argparse.Namespace) -> None:
    if args.id is None and args.find is None:
        print("notes update: provide ID or --find TITLE", file=sys.stderr)
        sys.exit(1)
    note = Note.get(args.session, args.id) if args.id is not None else Note.find(args.session, args.find)
    if note is None:
        print("Note not found.", file=sys.stderr)
        sys.exit(1)
    body = resolve_text_arg(args.body) if args.body is not None else None
    if args.append is not None or args.replace is not None:
        replace = tuple(args.replace) if args.replace is not None else None
        body = apply_text_edit(note.body, f"body of {note.title!r}", args.append, replace)
    collection = _resolve_collection(args.collection)
    note.update(title=args.title, body=body, tags=args.tags, collection=collection)
    args.session.commit()
    print(f"Updated: {note}")


def cmd_delete(args: argparse.Namespace) -> None:
    note = apply_soft_delete(args.session, Note, args.id, "Note")
    args.session.commit()
    print(f"Note #{note.id} {note.title!r}: soft-deleted (restore with `kb notes restore {note.id}`)")


def cmd_restore(args: argparse.Namespace) -> None:
    note = apply_restore(args.session, Note, args.id, "Note")
    args.session.commit()
    print(f"Note #{note.id} {note.title!r}: restored")


def cmd_purge(args: argparse.Namespace) -> None:
    note = apply_purge(args.session, Note, args.id, "Note", args.force_delete_links)
    args.session.commit()
    print(f"Note #{note.id} {note.title!r}: purged (irreversible)")


def cmd_reembed(args: argparse.Namespace) -> None:
    from embed import model_name

    notes = args.session.scalars(select(Note)).all()
    if not notes:
        print("No notes to reembed.")
        return
    print(f"Reembedding {len(notes)} notes with model '{model_name()}'...")
    for i, note in enumerate(notes, 1):
        note.reembed()
        print(f"  [{i}/{len(notes)}] {note.title!r}")
    args.session.commit()
    print("Done.")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("notes", aliases=["n", "note"], help="Note operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show a note by id")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a note")
    p_add.add_argument("title")
    p_add.add_argument(
        "body",
        nargs="?",
        default=None,
        help="Note body -- provide this OR --body-file, not both. '-' reads from stdin.",
    )
    p_add.add_argument(
        "--body-file",
        metavar="FILE",
        help="Read the note body from FILE instead of the BODY positional -- provide this OR BODY, not both. "
        "'-' reads from stdin. Prefer this for long/multiline bodies over shell-quoting BODY directly.",
    )
    p_add.add_argument("--tags", default=None, help="Comma-separated tags")
    p_add.add_argument(
        "--collection",
        default=None,
        help="Collection to file the note under (default: inbox). Unknown names fall back to inbox with a warning.",
    )
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update a note by id or title")
    p_update.add_argument("id", type=int, nargs="?", help="Note id")
    p_update.add_argument("--find", metavar="TITLE", help="Find note by exact title, instead of ID")
    p_update.add_argument("--title", help="New title")
    p_update.add_argument("--body", help="Replace the entire body -- prefer --append/--replace for a small change")
    p_update.add_argument("--append", metavar="TEXT", help="Append a paragraph to the body without restating the rest")
    p_update.add_argument(
        "--replace",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Replace one occurrence of OLD with NEW in the body -- errors if OLD is missing or not unique",
    )
    p_update.add_argument("--tags", help="New tags (comma-separated)")
    p_update.add_argument(
        "--collection",
        default=None,
        help="Move the note to this collection. Unknown names fall back to inbox with a warning.",
    )
    p_update.set_defaults(func=cmd_update)

    p_search = sub.add_parser(
        "search",
        help="Removed -- use top-level `kb search` instead",
    )
    p_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    p_search.set_defaults(func=cmd_search_deprecated)

    p_reembed = sub.add_parser("reembed", help="Recompute embeddings for all notes")
    p_reembed.set_defaults(func=cmd_reembed)

    p_delete = sub.add_parser("delete", help="Soft-delete a note (reversible, see restore)")
    p_delete.add_argument("id", type=int)
    p_delete.set_defaults(func=cmd_delete)

    p_restore = sub.add_parser("restore", help="Undo a soft delete on a note")
    p_restore.add_argument("id", type=int)
    p_restore.set_defaults(func=cmd_restore)

    p_purge = sub.add_parser("purge", help="Permanently delete a note (irreversible)")
    p_purge.add_argument("id", type=int)
    p_purge.add_argument("--force-delete-links", action="store_true", help="Also delete any EntityLinks pointing at it")
    p_purge.set_defaults(func=cmd_purge)
