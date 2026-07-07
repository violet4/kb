"""Journal operations."""
import argparse

from models import Journal


def cmd_add(args: argparse.Namespace) -> None:
    entry = Journal.record(args.session, args.entity_type, args.entity_id, note=args.note)
    args.session.commit()
    print(entry)


def cmd_show(args: argparse.Namespace) -> None:
    entries = Journal.for_entity(args.session, args.entity_type, args.entity_id)
    if not entries:
        print("No journal entries.")
        return
    for i, e in enumerate(entries):
        if i > 0:
            print()
        when = e.created_at.strftime("%Y-%m-%d %H:%M")
        if e.field:
            print(f"[{when}] {e.field}: {e.old_value!r} -> {e.new_value!r}")
            if e.note:
                print(f"  {e.note}")
        else:
            print(f"[{when}] {e.note}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("journal", help="Journal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Record a free-text journal note for an entity")
    p_add.add_argument("entity_type")
    p_add.add_argument("entity_id", type=int)
    p_add.add_argument("note")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Show journal history for an entity")
    p_show.add_argument("entity_type")
    p_show.add_argument("entity_id", type=int)
    p_show.set_defaults(func=cmd_show)
