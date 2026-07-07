"""Context operations."""

import argparse

from sqlalchemy import select

from context import switch_current
from models import Context, CurrentContext


def cmd_current(args: argparse.Namespace) -> None:
    context = CurrentContext.get(args.session)
    print(context.name if context else "(none)")


def cmd_switch(args: argparse.Namespace) -> None:
    context = switch_current(args.session, args.name)
    args.session.commit()
    print(f"Current context: {context.name!r}")


def cmd_list(args: argparse.Namespace) -> None:
    contexts = args.session.scalars(select(Context).order_by(Context.name)).all()
    if not contexts:
        print("No contexts yet.")
        return
    current = CurrentContext.get(args.session)
    for c in contexts:
        marker = " (current)" if current and current.id == c.id else ""
        print(f"#{c.id} {c.name}{marker}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("context", help="Context operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_current = sub.add_parser("current", help="Show the active context")
    p_current.set_defaults(func=cmd_current)

    p_switch = sub.add_parser("switch", help="Change the active context")
    p_switch.add_argument("name")
    p_switch.set_defaults(func=cmd_switch)

    p_list = sub.add_parser("list", help="List all known contexts")
    p_list.set_defaults(func=cmd_list)
