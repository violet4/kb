"""Instruction tree operations -- see Instruction's docstring in models.py and kb Goal #23
for the full design. Five commands, mirroring real usage: `root`/`show` for walking the
tree (cheap, read-heavy, the common case), `add`/`set-parent`/`edit` for growing and
restructuring it, `tree` for a full dump.

Every node reference (a positional target, or --parent) accepts a title, not a bare id --
ids exist for disambiguation and machine bookkeeping, not as the primary way a human
composes a command. Prefix with '#' to reference by id instead (e.g. when two nodes
share a title and the ref is ambiguous).
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Instruction

from kb_cli._util import apply_text_edit
from kb_cli.search import search_entities


def _print_node(session: Session, node: Instruction, show_body: bool) -> None:
    trigger_line = f"\ntrigger: {node.trigger}" if node.trigger else ""
    print(f"#{node.id} {node.title}{trigger_line}")
    if show_body:
        print()
        print(node.body)
    children = Instruction.children(session, node.id)
    if children:
        print()
        print("children:")
        for c in children:
            marker = f"  (trigger: {c.trigger})" if c.trigger else ""
            print(f"  {c.title} #{c.id}{marker}")


def _resolve(session: Session, ref: str) -> Instruction:
    """Resolve a node reference: '#ID' for an exact id, otherwise a title lookup.
    Errors (rather than guessing) on no match or an ambiguous title, since a silent
    wrong pick when restructuring the tree is worse than a rejected command."""
    if ref.startswith("#"):
        node = session.get(Instruction, int(ref[1:]))
        if node is None:
            print(f"Instruction {ref}: not found", file=sys.stderr)
            sys.exit(1)
        return node

    matches = session.scalars(select(Instruction).where(Instruction.title == ref)).all()
    if not matches:
        print(f"Instruction {ref!r}: not found", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        options = ", ".join(f"#{m.id}" for m in matches)
        print(
            f"Instruction {ref!r} is ambiguous ({len(matches)} matches: {options}) -- use #ID instead", file=sys.stderr
        )
        sys.exit(1)
    return matches[0]


def cmd_root(args: argparse.Namespace) -> None:
    roots = Instruction.roots(args.session)
    if not roots:
        print("No Instruction nodes yet -- create one with: kb instructions add TITLE ...")
        return
    if len(roots) == 1:
        _print_node(args.session, roots[0], show_body=True)
        return
    print("Multiple root nodes:")
    for r in roots:
        marker = f"  (trigger: {r.trigger})" if r.trigger else ""
        print(f"  {r.title} #{r.id}{marker}")


def cmd_show(args: argparse.Namespace) -> None:
    node = _resolve(args.session, args.ref)
    _print_node(args.session, node, show_body=True)


def cmd_add(args: argparse.Namespace) -> None:
    parent = _resolve(args.session, args.parent) if args.parent is not None else None
    node = Instruction(title=args.title, body=args.body, trigger=args.trigger, parent=parent, context=args.context)
    args.session.add(node)
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_set_parent(args: argparse.Namespace) -> None:
    node = _resolve(args.session, args.ref)
    node.parent = _resolve(args.session, args.parent) if args.parent is not None else None
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_edit(args: argparse.Namespace) -> None:
    node = _resolve(args.session, args.ref)
    if args.title is not None:
        node.title = args.title
    if args.body is not None:
        node.body = args.body
    if args.append is not None or args.replace is not None:
        replace = tuple(args.replace) if args.replace is not None else None
        node.body = apply_text_edit(node.body, f"body of {node.title!r}", args.append, replace)
    if args.trigger is not None:
        node.trigger = None if args.trigger == "" else args.trigger
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_delete(args: argparse.Namespace) -> None:
    node = _resolve(args.session, args.ref)
    children = Instruction.children(args.session, node.id)
    if children and not args.reparent_children:
        titles = ", ".join(c.title for c in children)
        print(
            f"Instruction {node.title!r} has children ({titles}) -- pass --reparent-children to move them "
            "up to this node's own parent before deleting, or delete/move them first",
            file=sys.stderr,
        )
        sys.exit(1)
    for child in children:
        child.parent = node.parent
    args.session.delete(node)
    args.session.commit()
    print(f"Deleted Instruction #{node.id} {node.title!r}")


def cmd_search(args: argparse.Namespace) -> None:
    results = search_entities(args.session, (Instruction,), args.query)
    if not results:
        print("No matches.")
        return
    for node in results:
        print(repr(node))


def cmd_tree(args: argparse.Namespace) -> None:
    all_nodes = args.session.scalars(select(Instruction)).all()
    if not all_nodes:
        print("No Instruction nodes yet -- create one with: kb instructions add TITLE ...")
        return

    children: dict[int | None, list[Instruction]] = {}
    for n in all_nodes:
        children.setdefault(n.parent_id, []).append(n)
    for kids in children.values():
        kids.sort(key=lambda n: n.title)

    def render(node: Instruction, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        trigger_str = f"  (trigger: {node.trigger})" if node.trigger else ""
        body_str = f"\n{prefix}{'    ' if is_last else '│   '}{node.body}" if args.bodies else ""
        print(f"{prefix}{branch}{node.title} #{node.id}{trigger_str}{body_str}")
        extension = "    " if is_last else "│   "
        kids = children.get(node.id, [])
        for i, kid in enumerate(kids):
            render(kid, prefix + extension, i == len(kids) - 1)

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("instructions", help="Instruction tree operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_root = sub.add_parser("root", help="Show the root node(s) -- entry point into the tree")
    p_root.set_defaults(func=cmd_root)

    p_show = sub.add_parser("show", help="Show one node's full body plus its children")
    p_show.add_argument("ref", metavar="TITLE|#ID", help="Node title, or #ID if the title is ambiguous")
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a node to the Instruction tree")
    p_add.add_argument("title")
    p_add.add_argument("body")
    p_add.add_argument("--parent", metavar="TITLE|#ID", help="Parent node (omit for a root node)")
    p_add.add_argument("--trigger", help='"If/when ..." condition; omit for an always-relevant node')
    p_add.set_defaults(func=cmd_add)

    p_set_parent = sub.add_parser("set-parent", help="Change (or clear) a node's parent")
    p_set_parent.add_argument("ref", metavar="TITLE|#ID")
    p_set_parent.add_argument("--parent", metavar="TITLE|#ID", help="Omit to clear the parent (make it a root node)")
    p_set_parent.set_defaults(func=cmd_set_parent)

    p_edit = sub.add_parser("edit", help="Edit a node's title, body, or trigger")
    p_edit.add_argument("ref", metavar="TITLE|#ID")
    p_edit.add_argument("--title")
    p_edit.add_argument("--body", help="Replace the entire body -- prefer --append/--replace for a small change")
    p_edit.add_argument("--append", metavar="TEXT", help="Append a paragraph to the body without restating the rest")
    p_edit.add_argument(
        "--replace",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Replace one occurrence of OLD with NEW in the body -- errors if OLD is missing or not unique",
    )
    p_edit.add_argument("--trigger", help='New "if/when ..." condition; pass "" to clear it')
    p_edit.set_defaults(func=cmd_edit)

    p_delete = sub.add_parser("delete", help="Delete a node (must have no children, unless --reparent-children)")
    p_delete.add_argument("ref", metavar="TITLE|#ID")
    p_delete.add_argument(
        "--reparent-children",
        action="store_true",
        help="Move this node's children up to its own parent before deleting, instead of refusing",
    )
    p_delete.set_defaults(func=cmd_delete)

    p_search = sub.add_parser(
        "search",
        help="Substring search over node titles/bodies -- the fallback when tree navigation doesn't surface something",
    )
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_tree = sub.add_parser("tree", help="Full tree dump, titles only by default")
    p_tree.add_argument("--bodies", action="store_true", help="Also print each node's full body inline")
    p_tree.set_defaults(func=cmd_tree)
