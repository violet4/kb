"""Instruction tree operations -- see Instruction's docstring in models.py and kb Goal #23
for the full design. Four commands, mirroring real usage: `show` for walking the tree
(cheap, read-heavy, the common case -- `show root` is the entry point, with no separate
`root` subcommand, so there's exactly one verb to reach for), `add`/`set-parent`/`edit`
for growing and restructuring it, `tree` for a full dump.

Every node reference (a positional target, or --parent) accepts either a title or a bare
id -- both are checked, '#' prefix accepted but optional, and "root" resolves to the
tree's entry point instead of a literal title lookup (see _resolve_ref). Instruction.title
is unique at the DB level and can never be purely numeric or literally "root" (enforced at
add/edit time), so a ref can only ever match at most one node -- resolving is a plain
found-or-not-found lookup, never an ambiguous-match situation.
"""

import argparse
import sys
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import EntityLink, Instruction

from kb_cli._util import apply_text_edit, check_no_links, print_links, resolve_text_arg
from kb_cli.search import cmd_search_one


def _size_line(node: Instruction) -> str:
    """Body size in chars, always shown after a write -- catches a duplicate-content
    mistake (an --append/--replace chain that didn't do what was intended) immediately,
    instead of only being noticed later via `kb instructions show root | wc -c`. Plain size
    report, no threshold -- there was previously a warning tied to Claude Code's
    SessionStart hook's 10,000-char stdout cap, but that hook has since been removed
    (see kb Goal #23: the bootstrap now runs `kb instructions show root` as an ordinary tool
    call, not hook-injected stdout), so no such limit currently applies."""
    return f"body: {len(node.body)} chars"


def _trigger_marker(node: Instruction) -> str:
    trigger = f"  (trigger: {node.trigger})" if node.trigger else ""
    system = "  [system]" if node.system_level else ""
    return f"{trigger}{system}"


def _link_filter(session: Session, instructions_only: bool, system_only: bool) -> Optional[Callable[[str, int], bool]]:
    """Builds the (other_type, other_id) -> bool predicate for print_links's other_filter,
    from --instructions-only/--system-only. Returns None (no filtering) when both are False,
    the default -- show every linked node, matching kb i show root's current framing that
    reachable connections should be cheap to see, not gated behind flags by default."""
    if not instructions_only and not system_only:
        return None

    def accept(other_type: str, other_id: int) -> bool:
        if instructions_only and other_type != "Instruction":
            return False
        if system_only:
            if other_type != "Instruction":
                return False
            other = session.get(Instruction, other_id)
            if other is None or not other.system_level:
                return False
        return True

    return accept


def _print_node(
    session: Session, node: Instruction, show_body: bool, instructions_only: bool = False, system_only: bool = False
) -> None:
    trigger_line = f"\ntrigger: {node.trigger}" if node.trigger else ""
    print(f"#{node.id} {node.title}{trigger_line}")
    if node.system_level:
        print("system_level: true")
    print(_size_line(node))
    if show_body:
        print()
        print(node.body)
    children = Instruction.children(session, node.id)
    if children:
        print()
        print("children:")
        for c in children:
            print(f"  {c.title} #{c.id}{_trigger_marker(c)}")
    if show_body:
        print_links(session, "Instruction", node.id, other_filter=_link_filter(session, instructions_only, system_only))


def _check_title_valid(title: str) -> None:
    """Reject a pure-digit title, so a title can never collide with an id in _resolve's
    dual lookup, and reject the literal title "root", the one reserved keyword _resolve_ref
    treats specially (see its docstring) -- a node titled "root" would be permanently
    unreachable by name, shadowed by that special case. TODO: root-handling should be
    centralized further (kb todo); this guard only prevents the specific title collision,
    it doesn't own "root" semantics."""
    if title.isdigit():
        print(f"Instruction title {title!r}: titles can't be purely numeric (ambiguous with an id)", file=sys.stderr)
        sys.exit(1)
    if title == "root":
        print(
            "Instruction title 'root': reserved -- refers to the tree's entry point in `kb i show root`",
            file=sys.stderr,
        )
        sys.exit(1)


def _resolve(session: Session, ref: str) -> Optional[Instruction]:
    """Resolve a node reference by id or by title, whichever matches -- '#' prefix is
    accepted but no longer required. Instruction.title is unique at the DB level, so at
    most one of id/title lookup can ever match; returns None, not an exception or exit,
    when nothing matches -- a user-supplied ref not being found is a normal outcome, not
    a program error, so the caller decides what to do with it (print a message, exit,
    treat as a plain boolean)."""
    bare = ref[1:] if ref.startswith("#") else ref
    if bare.isdigit():
        by_id = session.get(Instruction, int(bare))
        if by_id is not None:
            return by_id
    return session.scalars(select(Instruction).where(Instruction.title == ref)).first()


def _resolve_ref(session: Session, ref: str) -> Optional[Instruction]:
    """The one place that knows "root" is a reserved ref meaning the tree's entry point
    (Instruction.roots()), rather than a literal title lookup -- every caller that accepts
    a node reference goes through this, not _resolve directly, so "root" behaves the same
    way everywhere (show, add --parent, set-parent --parent, edit). Title uniqueness means
    there's at most one root node in the common case; falls through to None (not-found) if
    there are zero or, from stale/pre-constraint data, more than one."""
    if ref == "root":
        roots = Instruction.roots(session)
        return roots[0] if len(roots) == 1 else None
    return _resolve(session, ref)


def _resolve_or_exit(session: Session, ref: str) -> Instruction:
    """The command-boundary counterpart to _resolve_ref -- every cmd_* that needs exactly
    one existing node to proceed (not cmd_show, which handles multiple refs and partial
    failure itself) calls this instead of _resolve_ref directly, so "not found" prints a
    message and exits in one place rather than each command re-writing that check."""
    node = _resolve_ref(session, ref)
    if node is None:
        print(f"Instruction {ref!r}: not found", file=sys.stderr)
        sys.exit(1)
    return node


def cmd_show(args: argparse.Namespace) -> None:
    any_failed = False
    nodes: list[Instruction] = []
    for i, ref in enumerate(args.refs):
        if i > 0:
            print()
        node = _resolve_ref(args.session, ref)
        if node is None:
            print(ref)
            print("not found", file=sys.stderr)
            any_failed = True
        else:
            nodes.append(node)
            _print_node(
                args.session,
                node,
                show_body=True,
                instructions_only=args.instructions_only,
                system_only=args.system_only,
            )
    if len(nodes) > 1:
        _print_merged_children(args.session, nodes)
    if any_failed:
        sys.exit(1)


def _print_merged_children(session: Session, nodes: list[Instruction]) -> None:
    """When two or more ids are shown at once, a child shared by several of them (e.g. two
    domain nodes both parented under the same subtopic) would otherwise print once per parent
    under each node's own children list above -- easy to miss as "the same node" when it's
    repeated. This prints one deduplicated cross-reference section instead, each child listed
    once with every given node it belongs to, so the shared structure across the requested ids
    is visible at a glance rather than reconstructed by the reader."""
    shown_ids = {n.id for n in nodes}
    child_to_parents: dict[int, list[Instruction]] = {}
    child_nodes: dict[int, Instruction] = {}
    for n in nodes:
        for c in Instruction.children(session, n.id):
            child_to_parents.setdefault(c.id, []).append(n)
            child_nodes[c.id] = c
    shared = {cid: parents for cid, parents in child_to_parents.items() if len(parents) > 1}
    if not shared:
        return
    print()
    print(f"shared children across {', '.join(str(n.id) for n in nodes if n.id in shown_ids)}:")
    for cid, parents in shared.items():
        c = child_nodes[cid]
        parent_titles = ", ".join(p.title for p in parents)
        print(f"  {c.title} #{c.id}{_trigger_marker(c)}  (child of: {parent_titles})")


def _clear_parent_link(session: Session, node: Instruction) -> None:
    """Delete node's own incoming "parent-of" EntityLink, if any -- the graph-backed
    equivalent of the old `node.parent = None` FK assignment."""
    existing = session.scalars(
        select(EntityLink).where(
            EntityLink.type_b == "Instruction",
            EntityLink.id_b == node.id,
            EntityLink.relation == Instruction._PARENT_RELATION,
        )
    ).first()
    if existing is not None:
        session.delete(existing)


def _set_parent_link(session: Session, node: Instruction, parent: Optional[Instruction]) -> None:
    """Replace node's own "parent-of" EntityLink with one pointing at `parent` (or none, if
    `parent` is None) -- the graph-backed equivalent of the old `node.parent = X` FK
    assignment. A node has at most one incoming parent-of edge by construction here, even
    though the schema itself doesn't enforce that (see Instruction.parent's docstring)."""
    _clear_parent_link(session, node)
    if parent is not None:
        session.flush()
        EntityLink.create(session, "Instruction", parent.id, "Instruction", node.id, Instruction._PARENT_RELATION)


def cmd_add(args: argparse.Namespace) -> None:
    _check_title_valid(args.title)
    if _resolve(args.session, args.title) is not None:
        print(f"Instruction title {args.title!r}: already exists -- titles must be unique", file=sys.stderr)
        sys.exit(1)
    parent = _resolve_or_exit(args.session, args.parent) if args.parent is not None else None
    node = Instruction(
        title=args.title,
        body=resolve_text_arg(args.body),
        trigger=args.trigger,
        system_level=args.system_level,
        context=args.context,
    )
    node.reembed()
    args.session.add(node)
    args.session.flush()
    if parent is not None:
        EntityLink.create(args.session, "Instruction", parent.id, "Instruction", node.id, Instruction._PARENT_RELATION)
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_set_parent(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.session, args.ref)
    parent = _resolve_or_exit(args.session, args.parent) if args.parent is not None else None
    _set_parent_link(args.session, node, parent)
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_edit(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.session, args.ref)
    if args.title is not None:
        _check_title_valid(args.title)
        existing = _resolve(args.session, args.title)
        if existing is not None and existing.id != node.id:
            print(f"Instruction title {args.title!r}: already exists -- titles must be unique", file=sys.stderr)
            sys.exit(1)
        node.title = args.title
    if args.body is not None:
        node.body = resolve_text_arg(args.body)
    if args.append is not None or args.replace is not None:
        replace = tuple(args.replace) if args.replace is not None else None
        node.body = apply_text_edit(node.body, f"body of {node.title!r}", args.append, replace)
    if args.trigger is not None:
        node.trigger = None if args.trigger == "" else args.trigger
    if args.system_level is not None:
        node.system_level = args.system_level
    args.session.commit()
    _print_node(args.session, node, show_body=False)


def cmd_delete(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.session, args.ref)
    children = Instruction.children(args.session, node.id)
    if children and not args.reparent_children:
        titles = ", ".join(c.title for c in children)
        print(
            f"Instruction {node.title!r} has children ({titles}) -- pass --reparent-children to move them "
            "up to this node's own parent before deleting, or delete/move them first",
            file=sys.stderr,
        )
        sys.exit(1)
    grandparent = Instruction.parent(args.session, node.id)
    for child in children:
        _set_parent_link(args.session, child, grandparent)
    _clear_parent_link(args.session, node)
    args.session.flush()
    check_no_links(args.session, "Instruction", node.id, args.force_delete_links)
    args.session.delete(node)
    args.session.commit()
    print(f"Deleted Instruction #{node.id} {node.title!r}")


def cmd_tree(args: argparse.Namespace) -> None:
    all_nodes = args.session.scalars(select(Instruction)).all()
    if not all_nodes:
        print("No Instruction nodes yet -- create one with: kb instructions add TITLE ...")
        return

    parent_links = args.session.scalars(
        select(EntityLink).where(
            EntityLink.type_a == "Instruction", EntityLink.relation == Instruction._PARENT_RELATION
        )
    ).all()
    parent_id_by_child_id = {link.id_b: link.id_a for link in parent_links}

    children: dict[int | None, list[Instruction]] = {}
    for n in all_nodes:
        children.setdefault(parent_id_by_child_id.get(n.id), []).append(n)
    for kids in children.values():
        kids.sort(key=lambda n: n.title)

    def render(node: Instruction, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        body_str = f"\n{prefix}{'    ' if is_last else '│   '}{node.body}" if args.bodies else ""
        print(f"{prefix}{branch}{node.title} #{node.id}{_trigger_marker(node)}{body_str}")
        extension = "    " if is_last else "│   "
        kids = children.get(node.id, [])
        for i, kid in enumerate(kids):
            render(kid, prefix + extension, i == len(kids) - 1)

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("instructions", aliases=["i"], help="Instruction tree operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show one or more nodes' full body plus their children")
    p_show.add_argument(
        "refs",
        metavar="TITLE|#ID|root",
        nargs="+",
        help="One or more node titles or ids ('#' prefix optional); 'root' shows the entry point",
    )
    p_show.add_argument(
        "--instructions-only",
        action="store_true",
        help="In the printed links section, only show links to other Instruction nodes (hide links to Notes/Goals/etc.)",
    )
    p_show.add_argument(
        "--system-only",
        action="store_true",
        help="In the printed links section, only show links to system_level Instruction nodes (implies --instructions-only)",
    )
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a node to the Instruction tree")
    p_add.add_argument("title")
    p_add.add_argument("body")
    p_add.add_argument("--parent", metavar="TITLE|#ID", help="Parent node (omit for a root node)")
    p_add.add_argument("--trigger", help='"If/when ..." condition; omit for an always-relevant node')
    p_add.add_argument(
        "--system-level",
        dest="system_level",
        action="store_true",
        help="Mark as a candidate for the eventual kb si (filesystem-shippable) split -- see kb Todo #101",
    )
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
    system_level_group = p_edit.add_mutually_exclusive_group()
    system_level_group.add_argument(
        "--system-level", dest="system_level", action="store_true", default=None, help="Mark as system-level"
    )
    system_level_group.add_argument(
        "--no-system-level", dest="system_level", action="store_false", help="Clear system-level"
    )
    p_edit.set_defaults(func=cmd_edit)

    p_delete = sub.add_parser("delete", help="Delete a node (must have no children, unless --reparent-children)")
    p_delete.add_argument("ref", metavar="TITLE|#ID")
    p_delete.add_argument(
        "--reparent-children",
        action="store_true",
        help="Move this node's children up to its own parent before deleting, instead of refusing",
    )
    p_delete.add_argument(
        "--force-delete-links",
        action="store_true",
        help="Delete any EntityLinks pointing at this node first, instead of refusing",
    )
    p_delete.set_defaults(func=cmd_delete)

    p_search = sub.add_parser(
        "search",
        help="Substring plus semantic search over node titles/bodies -- the fallback when tree navigation "
        "doesn't surface something",
    )
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.set_defaults(func=cmd_search_one, model=Instruction)

    p_tree = sub.add_parser("tree", help="Full tree dump, titles only by default")
    p_tree.add_argument("--bodies", action="store_true", help="Also print each node's full body inline")
    p_tree.set_defaults(func=cmd_tree)
