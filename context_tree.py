"""Generic tree(1)-style renderer for items nested under the Context tree.

Extracted from kb_cli/todo.py's cmd_tree so any item type addressable by
context_id/tag_id (Todo, Timer, ...) can render the same way without duplicating
the tree-walk. A tag-addressed item prints under every Context in the tree that
carries that tag, not just once, so it's visible wherever it's actually
actionable without having to check another location's list.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Context


def render_context_tree(
    session: Session,
    items: Sequence[Any],
    line_for: Callable[[Any], str],
) -> Sequence[Any]:
    """Print `items` (each with .context_id/.tag_id) nested under the Context tree.

    line_for formats a single item's leaf line (no branch prefix -- that's added here).
    Returns the items that had neither a context_id nor a tag_id, so callers can
    report them separately.
    """
    contexts = session.scalars(select(Context)).all()

    children: dict[Any, list[Context]] = {}
    for c in contexts:
        children.setdefault(c.parent_id, []).append(c)
    for kids in children.values():
        kids.sort(key=lambda c: c.name)

    by_context_id: dict[int, list[Any]] = {}
    by_tag_id: dict[int, list[Any]] = {}
    unplaced: list[Any] = []
    for item in items:
        if item.context_id is not None:
            by_context_id.setdefault(item.context_id, []).append(item)
        elif item.tag_id is not None:
            by_tag_id.setdefault(item.tag_id, []).append(item)
        else:
            unplaced.append(item)

    def render(node: Context, prefix: str, is_last: bool) -> None:
        branch = "└── " if is_last else "├── "
        tag_str = f" [{', '.join(t.name for t in node.tags)}]" if node.tags else ""
        print(f"{prefix}{branch}{node.name}{tag_str}")
        extension = "    " if is_last else "│   "

        here = list(by_context_id.get(node.id, []))
        for tag in node.tags:
            here.extend(by_tag_id.get(tag.id, []))

        kids = children.get(node.id, [])
        for i, item in enumerate(here):
            is_leaf_last = (i == len(here) - 1) and not kids
            leaf_branch = "└── " if is_leaf_last else "├── "
            print(f"{prefix}{extension}{leaf_branch}{line_for(item)}")

        for i, kid in enumerate(kids):
            render(kid, prefix + extension, i == len(kids) - 1)

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        render(root, "", i == len(roots) - 1)

    return unplaced
