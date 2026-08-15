"""Generic entity-link (knowledge graph) operations -- see EntityLink's docstring in models.py.

Every entity is addressed as TYPE:ID (e.g. Goal:34, Todo:102) -- the same entity_type string
Journal already uses (a mapped class's own __name__), since most kb entities have no unique
name to look up by, only an id.
"""

import argparse
import sys
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kb_cli._util import describe_entity_ref as describe
from models import EntityLink

REF_HELP = "Entity reference in TYPE:ID form, e.g. Goal:34 or Todo:102"


def parse_ref(ref: str) -> tuple[str, int]:
    entity_type, _, id_str = ref.partition(":")
    if not id_str:
        print(f"{ref!r}: expected TYPE:ID form, e.g. Goal:34", file=sys.stderr)
        sys.exit(1)
    try:
        return entity_type, int(id_str)
    except ValueError:
        print(f"{ref!r}: {id_str!r} is not a valid id", file=sys.stderr)
        sys.exit(1)


def cmd_add(args: argparse.Namespace) -> None:
    if not args.relation.strip():
        print("--relation must be a non-empty string", file=sys.stderr)
        sys.exit(1)
    type_a, id_a = parse_ref(args.a)
    type_b, id_b = parse_ref(args.b)
    try:
        link = EntityLink.create(args.session, type_a, id_a, type_b, id_b, args.relation, note=args.note)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except IntegrityError:
        args.session.rollback()
        print(f"Link already exists: {args.a} --{args.relation}-- {args.b}", file=sys.stderr)
        sys.exit(1)
    args.session.commit()
    print(link)


def cmd_rm(args: argparse.Namespace) -> None:
    link = args.session.get(EntityLink, args.id)
    if link is None:
        print(f"EntityLink #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    # Print the full link, including note, before it's gone -- this is the only record of
    # exactly what was deleted, and the only way to re-create it (`kb link add A B --relation
    # "..."`) without digging through a DB backup.
    recreate = f"kb link add {link.type_a}:{link.id_a} {link.type_b}:{link.id_b} --relation {link.relation!r}"
    if link.note:
        recreate += f" --note {link.note!r}"
    print(f"Deleted {link!r}")
    print(f"To re-create: {recreate}")
    args.session.delete(link)
    args.session.commit()


def cmd_show(args: argparse.Namespace) -> None:
    """BFS from the root ref, depth-limited (default 1 hop), rendered tree(1)-style. A node
    already expanded earlier in this render is printed once as a '<-> (see above)' leaf on
    later encounters instead of re-expanded -- handles cycles and diamonds in the graph
    (which, unlike Context's tree, this is not restricted to being free of) and keeps the
    render finite. Sibling links at each node are sorted by (relation, type, id) so the same
    graph state always renders identically, regardless of insertion order."""
    root_type, root_id = parse_ref(args.ref)
    if EntityLink.resolve(args.session, root_type, root_id) is None:
        print(f"{args.ref}: not found", file=sys.stderr)
        sys.exit(1)

    print(describe(args.session, root_type, root_id))
    visited = {(root_type, root_id)}

    def render(node_type: str, node_id: int, depth: int, prefix: str) -> None:
        links = EntityLink.for_entity(args.session, node_type, node_id)
        # Sort (other_side, link) pairs together -- sorting entries and links separately
        # desyncs their indices, pairing each other_side with the wrong link/relation.
        pairs = sorted(((link.other_side(node_type, node_id), link) for link in links), key=lambda p: p[0])
        for i, ((other_type, other_id), link) in enumerate(pairs):
            is_last = i == len(pairs) - 1
            branch = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            # relation reads a-to-b (see EntityLink docstring) -- when the current node is b,
            # the arrow into it must point backward (<--) or the direction is misrepresented.
            arrow = (
                f"--{link.relation}-->" if (node_type, node_id) == (link.type_a, link.id_a) else f"<--{link.relation}--"
            )
            if (other_type, other_id) in visited:
                print(f"{prefix}{branch}{arrow} {other_type}:{other_id} (see above)")
                continue
            print(f"{prefix}{branch}{arrow} {describe(args.session, other_type, other_id)}")
            if depth < args.depth:
                visited.add((other_type, other_id))
                render(other_type, other_id, depth + 1, child_prefix)

    render(root_type, root_id, 1, "")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("link", help="Generic entity-link graph -- link any two kb rows, traverse them")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Create a link between two entities")
    p_add.add_argument("a", metavar="A", help=REF_HELP)
    p_add.add_argument("b", metavar="B", help=REF_HELP)
    p_add.add_argument("--relation", required=True, help="Non-empty label for what this link means, e.g. 'cites'")
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("rm", help="Delete a link by its own id")
    p_rm.add_argument("id", type=int)
    p_rm.set_defaults(func=cmd_rm)

    p_show = sub.add_parser("show", help="Show the link graph from a starting entity, 1 hop deep by default")
    p_show.add_argument("ref", metavar="TYPE:ID", help=REF_HELP)
    p_show.add_argument("--depth", type=int, default=1, help="How many hops to expand (default 1)")
    p_show.set_defaults(func=cmd_show)
