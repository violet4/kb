"""Context operations."""

import argparse
from typing import Any

from sqlalchemy import select

from context import KB_CONTEXT_ENV_VAR, switch_current
from models import Context, CurrentContext


def cmd_current(args: argparse.Namespace) -> None:
    context = CurrentContext.get(args.session)
    print(context.name if context else "(none)")


def cmd_add(args: argparse.Namespace) -> None:
    context = Context.get_or_create(args.session, args.name, description=args.description)
    args.session.commit()
    print(context)


def cmd_switch(args: argparse.Namespace) -> None:
    if args.local:
        # Print an export line rather than touching the DB, ssh-agent style --
        # eval "$(kb context switch NAME --local)" scopes the switch to this shell only.
        print(f"export {KB_CONTEXT_ENV_VAR}={args.name}")
        return
    context = switch_current(args.session, args.name)
    args.session.commit()
    print(f"Current context: {context.name!r}")


def cmd_clear(args: argparse.Namespace) -> None:
    if args.local:
        print(f"unset {KB_CONTEXT_ENV_VAR}")
        return
    CurrentContext.set(args.session, None)
    args.session.commit()
    print("Current context cleared.")


def cmd_list(args: argparse.Namespace) -> None:
    contexts = args.session.scalars(select(Context).order_by(Context.name)).all()
    if not contexts:
        print("No contexts yet.")
        return
    current = CurrentContext.get(args.session)
    for c in contexts:
        marker = " (current)" if current and current.id == c.id else ""
        print(f"#{c.id} {c.name}{marker}")


def cmd_tree(args: argparse.Namespace) -> None:
    """Render contexts as a tree by nesting on their dot-separated name segments --
    purely a naming convention (see models.Context), not an enforced parent/child
    relationship, so a context can appear "nested" here without any FK backing it."""
    contexts = args.session.scalars(select(Context).order_by(Context.name)).all()
    if not contexts:
        print("No contexts yet.")
        return
    current = CurrentContext.get(args.session)

    root: dict[str, Any] = {}
    for c in contexts:
        node = root
        for segment in c.name.split("."):
            node = node.setdefault(segment, {})
        node["__context__"] = c

    def render(node: dict[str, Any], prefix: str, depth: int) -> None:
        children = {k: v for k, v in node.items() if k != "__context__"}
        for i, (segment, child) in enumerate(sorted(children.items())):
            is_last = i == len(children) - 1
            branch = "└── " if is_last else "├── "
            c = child.get("__context__")
            marker = " (current)" if c is not None and current and current.id == c.id else ""
            label = segment if c is not None else f"{segment} (no such context)"
            print(f"{prefix}{branch}{label}{marker}")
            extension = "    " if is_last else "│   "
            render(child, prefix + extension, depth + 1)

    render(root, "", 0)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("context", help="Context operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_current = sub.add_parser("current", help="Show the active context")
    p_current.set_defaults(func=cmd_current)

    p_add = sub.add_parser("add", help="Create a new context")
    p_add.add_argument("name")
    p_add.add_argument("--description")
    p_add.set_defaults(func=cmd_add)

    p_switch = sub.add_parser("switch", help="Change the active context")
    p_switch.add_argument("name")
    p_switch.add_argument(
        "--local",
        action="store_true",
        help=f'Print `export {KB_CONTEXT_ENV_VAR}=NAME` instead of persisting -- eval "$(kb context switch NAME --local)" to scope the switch to this shell only',
    )
    p_switch.set_defaults(func=cmd_switch)

    p_clear = sub.add_parser("clear", help="Clear the active context")
    p_clear.add_argument(
        "--local",
        action="store_true",
        help=f'Print `unset {KB_CONTEXT_ENV_VAR}` instead -- eval "$(kb context clear --local)" to clear this shell\'s override only',
    )
    p_clear.set_defaults(func=cmd_clear)

    p_list = sub.add_parser("list", help="List all known contexts (flat)")
    p_list.set_defaults(func=cmd_list)

    p_tree = sub.add_parser("tree", help="List all known contexts, nested by dot-separated name")
    p_tree.set_defaults(func=cmd_tree)
