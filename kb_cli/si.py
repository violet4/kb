"""System instructions -- shipped with kb itself via git, not stored in the DB. Distinct
from `kb instructions` (`kb i`), which is one user's own Instruction tree in the DB:
personal context, overrides, anything a user has added. Content under
instructions_system/ is identical for anyone running this project and is versioned with
the code, same as any other file in this repo -- forking it is an ordinary git fork, not a
kb mechanism.

Full CRUD, not just read: `kb si` writes directly to instructions_system/'s files and
graph.json, the same way `kb i` writes directly to the DB -- there is no promote/export
step in between (a prior design draft this session proposed exactly that gate and was
explicitly overridden by the user: read/navigate/rearrange/create/update/delete all belong
here, operating on the files themselves). Every write command prints an explicit warning
distinguishing this from `kb i`'s per-user DB write path, since a `kb si` write changes
the git-tracked, shared-by-every-user copy, not personal state.

Command surface deliberately mirrors kb_cli/instruction.py's shape (show/add/edit/
set-parent/delete/tree) so the two feel like the same tool operating on two different
backing stores -- see that module's own docstring for the ref-resolution rules ('#'
optional, "root" reserved) this module reuses via kb_cli.si_files.resolve_ref.

See kb Goal #70 for the full design rationale and kb Note #283/#287 for the file-layout
and taxonomy research this implements."""

import argparse
import functools
import sys
from typing import Callable, Optional

from kb_cli import si_files as sf
from kb_cli._util import apply_replace_range, apply_text_edit, extract_range, resolve_text_arg

_SYSTEM_WRITE_WARNING = (
    "kb si: this writes instructions_system/ directly -- the git-tracked, shared-by-every-user "
    "system instruction tree, not your own personal kb i (DB) tree. Commit and review the diff "
    "like any other code change."
)


def _print_write_warning() -> None:
    print(_SYSTEM_WRITE_WARNING, file=sys.stderr)


def _trigger_marker(node: sf.SiNode) -> str:
    return f"  (trigger: {node.trigger})" if node.trigger else ""


def _size_line(node: sf.SiNode) -> str:
    return f"body: {len(node.body)} chars"


def _print_node(node: sf.SiNode, show_body: bool) -> None:
    trigger_line = f"\ntrigger: {node.trigger}" if node.trigger else ""
    print(f"#{node.id} {node.title}{trigger_line}")
    print(_size_line(node))
    if show_body:
        print()
        print(node.body)
    children = sf.children_of(node.id)
    if children:
        print()
        print("children:")
        for c in children:
            print(f"  {c.title} #{c.id}{_trigger_marker(c)}")


def _print_links(node: sf.SiNode) -> None:
    edges = sf.links_for(node.id)
    if not edges:
        return
    print(f"links: {len(edges)}")
    for e in edges:
        if e.from_id == node.id:
            print(f"  --{e.relation}--> #{e.to_id}")
        else:
            print(f"  <--{e.relation}-- #{e.from_id}")


def _check_title_valid(title: str) -> None:
    """Mirrors kb_cli.instruction._check_title_valid exactly: a title can't be purely
    numeric (ambiguous with an id in resolve()) or the literal "root" (reserved, see
    si_files.resolve_ref)."""
    if title.isdigit():
        print(f"kb si: title {title!r}: titles can't be purely numeric (ambiguous with an id)", file=sys.stderr)
        sys.exit(1)
    if title == "root":
        print("kb si: title 'root': reserved -- refers to the tree's entry point in `kb si show root`", file=sys.stderr)
        sys.exit(1)


def _resolve_or_exit(ref: str) -> sf.SiNode:
    node = sf.resolve_ref(ref)
    if node is None:
        print(f"kb si: {ref!r}: not found", file=sys.stderr)
        sys.exit(1)
    return node


def _handle_si_errors(func: Callable[[argparse.Namespace], None]) -> Callable[[argparse.Namespace], None]:
    """Every cmd_* is wrapped with this at registration (see add_subparser), rather than
    each function carrying its own try/except -- a malformed file on disk (a missing
    header, a corrupt graph.json) is a data problem any command can hit, not something
    specific to whichever command happened to trigger the read, so it has exactly one
    handler instead of one copy per command. Prints a clean stderr message and exits 1,
    matching every other kb_cli command's own "no raw traceback" convention -- si_files
    itself deliberately raises rather than silently returning a partial/guessed result on
    malformed input, so this is where that strictness turns into a normal CLI error."""

    @functools.wraps(func)
    def wrapped(args: argparse.Namespace) -> None:
        try:
            func(args)
        except sf.SiFilesError as e:
            print(f"kb si: {e}", file=sys.stderr)
            sys.exit(1)

    return wrapped


def cmd_show(args: argparse.Namespace) -> None:
    if args.extract is not None:
        if len(args.refs) != 1:
            print("--extract: pass exactly one node", file=sys.stderr)
            sys.exit(1)
        target = _resolve_or_exit(args.refs[0])
        result = extract_range(target.body, f"body of {target.title!r}", tuple(args.extract))
        print(result)
        return
    any_failed = False
    shown = 0
    for i, ref in enumerate(args.refs):
        if i > 0:
            print()
        node = sf.resolve_ref(ref)
        if node is None:
            print(ref)
            print("not found", file=sys.stderr)
            any_failed = True
            continue
        shown += 1
        _print_node(node, show_body=True)
        if args.links:
            _print_links(node)
    if any_failed:
        sys.exit(1)


def cmd_add(args: argparse.Namespace) -> None:
    _check_title_valid(args.title)
    if sf.resolve(args.title) is not None:
        print(f"kb si: title {args.title!r}: already exists -- titles must be unique", file=sys.stderr)
        sys.exit(1)
    parent = _resolve_or_exit(args.parent) if args.parent is not None else None
    node_id = sf.next_id()
    sf.save_node(node_id, args.title, args.trigger, resolve_text_arg(args.body))
    if parent is not None:
        sf.set_parent(node_id, parent.id)
    _print_write_warning()
    written = sf.resolve(node_id)
    assert written is not None, f"just wrote node {node_id!r}, resolve must find it"
    _print_node(written, show_body=False)


def cmd_set_parent(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.ref)
    parent = _resolve_or_exit(args.parent) if args.parent is not None else None
    sf.set_parent(node.id, parent.id if parent is not None else None)
    _print_write_warning()
    _print_node(node, show_body=False)


def cmd_edit(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.ref)
    title = node.title
    trigger = node.trigger
    body = node.body

    if args.title is not None:
        _check_title_valid(args.title)
        existing = sf.resolve(args.title)
        if existing is not None and existing.id != node.id:
            print(f"kb si: title {args.title!r}: already exists -- titles must be unique", file=sys.stderr)
            sys.exit(1)
        title = args.title
    if args.body is not None:
        body = resolve_text_arg(args.body)
    if args.append is not None or args.replace is not None:
        replace: Optional[tuple[str, str]] = tuple(args.replace) if args.replace is not None else None
        body = apply_text_edit(body, f"body of {title!r}", args.append, replace)
    if args.replace_range is not None:
        body = apply_replace_range(body, f"body of {title!r}", tuple(args.replace_range))
    if args.trigger is not None:
        trigger = None if args.trigger == "" else args.trigger

    old_path = node.path
    sf.save_node(node.id, title, trigger, body, old_path=old_path)
    _print_write_warning()
    written = sf.resolve(node.id)
    assert written is not None, f"just wrote node {node.id!r}, resolve must find it"
    _print_node(written, show_body=True)


def cmd_delete(args: argparse.Namespace) -> None:
    node = _resolve_or_exit(args.ref)
    children = sf.children_of(node.id)
    if children and not args.reparent_children:
        titles = ", ".join(c.title for c in children)
        print(
            f"kb si: {node.title!r} has children ({titles}) -- pass --reparent-children to move them "
            "up to this node's own parent before deleting, or delete/move them first",
            file=sys.stderr,
        )
        sys.exit(1)
    grandparent = sf.parent_of(node.id)
    for child in children:
        sf.set_parent(child.id, grandparent.id if grandparent is not None else None)
    sf.set_parent(node.id, None)
    remaining_links = [e for e in sf.links_for(node.id)]
    if remaining_links and not args.force_delete_links:
        print(
            f"kb si: {node.title!r} has {len(remaining_links)} remaining link(s) -- pass "
            "--force-delete-links to remove them first",
            file=sys.stderr,
        )
        sys.exit(1)
    if remaining_links:
        edges = [e for e in sf.load_graph() if e.from_id != node.id and e.to_id != node.id]
        sf.save_graph(edges)
    sf.delete_node_file(node)
    _print_write_warning()
    print(f"Deleted #{node.id} {node.title!r}")


def cmd_tree(args: argparse.Namespace) -> None:
    nodes = sf.list_nodes()
    if not nodes:
        print("No system instruction nodes yet -- create one with: kb si add TITLE ...")
        return
    graph = sf.load_graph()
    parent_id_by_child_id = {e.to_id: e.from_id for e in graph if e.relation == sf._PARENT_RELATION}

    by_parent: dict[Optional[str], list[sf.SiNode]] = {}
    for n in nodes:
        by_parent.setdefault(parent_id_by_child_id.get(n.id), []).append(n)
    for kids in by_parent.values():
        kids.sort(key=lambda n: n.title)

    def render(node: sf.SiNode, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        body_str = f"\n{prefix}{'    ' if is_last else '│   '}{node.body}" if args.bodies else ""
        print(f"{prefix}{branch}{node.title} #{node.id}{_trigger_marker(node)}{body_str}")
        extension = "    " if is_last else "│   "
        kids = by_parent.get(node.id, [])
        for i, kid in enumerate(kids):
            render(kid, prefix + extension, i == len(kids) - 1)

    roots = by_parent.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("si", help="System instructions (shipped with kb, same for every user)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show one or more nodes' full body plus their children")
    p_show.add_argument(
        "refs",
        metavar="TITLE|#ID|root",
        nargs="+",
        help="One or more node titles or ids ('#' prefix optional); 'root' shows the entry point",
    )
    p_show.add_argument("--links", action="store_true", help="Also print the node's links section")
    p_show.add_argument(
        "--extract",
        nargs=2,
        metavar=("BEGIN", "END"),
        help="Print only the span from the start of BEGIN's match through the end of END's match "
        "(inclusive), instead of the full body. Requires exactly one ref.",
    )
    p_show.set_defaults(func=_handle_si_errors(cmd_show))

    p_add = sub.add_parser("add", help="Add a node to the system instruction tree (writes instructions_system/)")
    p_add.add_argument("title")
    p_add.add_argument("body")
    p_add.add_argument("--parent", metavar="TITLE|#ID", help="Parent node (omit for a root node)")
    p_add.add_argument(
        "--trigger", required=True, help='"If/when ..." condition -- required, even a couple words beats none'
    )
    p_add.set_defaults(func=_handle_si_errors(cmd_add))

    p_set_parent = sub.add_parser("set-parent", help="Change (or clear) a node's parent")
    p_set_parent.add_argument("ref", metavar="TITLE|#ID")
    p_set_parent.add_argument("--parent", metavar="TITLE|#ID", help="Omit to clear the parent (make it a root node)")
    p_set_parent.set_defaults(func=_handle_si_errors(cmd_set_parent))

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
    p_edit.add_argument(
        "--replace-range",
        nargs=3,
        metavar=("START_SNIPPET", "END_SNIPPET", "NEW"),
        help="Replace everything from START_SNIPPET through END_SNIPPET (inclusive) with NEW",
    )
    p_edit.add_argument("--trigger", help='New "if/when ..." condition; pass "" to clear it')
    p_edit.set_defaults(func=_handle_si_errors(cmd_edit))

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
        help="Delete any graph edges pointing at this node first, instead of refusing",
    )
    p_delete.set_defaults(func=_handle_si_errors(cmd_delete))

    p_tree = sub.add_parser("tree", help="Full tree dump, titles only by default")
    p_tree.add_argument("--bodies", action="store_true", help="Also print each node's full body inline")
    p_tree.set_defaults(func=_handle_si_errors(cmd_tree))
