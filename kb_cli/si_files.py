"""File/graph I/O for kb si -- the flat-file, git-tracked mirror of kb_cli.instruction's
DB-backed Instruction tree. Every function here is pure file/JSON I/O with no argparse and
no DB session, so both kb_cli/si.py's CLI and any future non-CLI consumer (a doc generator,
a migration script) share one implementation of "what a node/graph file actually looks
like on disk" -- the same single-ownership discipline kb_cli/instruction.py already
applies to the DB-backed tree.

Storage shape, mirroring the DB tree's own split (Instruction rows + EntityLink rows) onto
the filesystem:
- One file per node: instructions_system/NNNN_slug.md, a 4-digit id prefix (this module's
  own id space, independent of Instruction.id -- see kb Note #283 for why) followed by a
  slugified title, then a small plain-text header (title/trigger, mirroring exactly what
  `kb i show` already prints for a node) and the body. The header never repeats the id --
  the filename IS the id, so there is exactly one place that fact lives, not two that can
  drift apart if a file is ever renamed.
- One graph file: instructions_system/graph.json, holding every edge (parent-of and any
  other relation) the same way EntityLink holds them for the DB tree -- type/id pairs are
  unnecessary here (every node in this graph is an Instruction-equivalent by construction,
  there is no other linkable type in this file-backed tree yet), so an edge is just
  {from, to, relation}, ids referring to this module's own NNNN id space.

Node references (a CLI positional, a --parent value) resolve by id or by title, exactly
mirroring kb_cli.instruction._resolve/_resolve_ref: '#' prefix optional, "root" is a
reserved ref meaning the tree's one entry point (the node with no incoming parent-of
edge), never a literal title lookup.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_SI_DIR = Path(__file__).resolve().parent.parent / "instructions_system"
_GRAPH_PATH = _SI_DIR / "graph.json"

_PARENT_RELATION = "parent-of"

_ID_WIDTH = 4

_FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.md$")

_HEADER_TITLE_RE = re.compile(r"^title:\s*(.*)$", re.MULTILINE)
_HEADER_TRIGGER_RE = re.compile(r"^trigger:\s*(.*)$", re.MULTILINE)


class SiFilesError(RuntimeError):
    """Raised for a caller mistake this module can't proceed past (a duplicate title, a
    missing node) -- kb_cli/si.py catches this at the command boundary and turns it into a
    stderr message + exit(1), the same shape kb_cli/instruction.py's own
    _resolve_or_exit/_check_title_valid already use for the DB-backed tree."""


@dataclass
class SiNode:
    """One node read from instructions_system/ -- the file-backed equivalent of an
    Instruction row. id/title/trigger/body mirror Instruction's own columns exactly;
    path is this node's own file, kept on the dataclass so a caller that already has a
    SiNode never needs to re-derive its path from id."""

    id: str  # the zero-padded NNNN string, e.g. "0001" -- kept as str (not int) since it's
    # a fixed-width filename component, not an arithmetic quantity.
    title: str
    trigger: Optional[str]
    body: str
    path: Path = field(compare=False)


@dataclass
class SiEdge:
    from_id: str
    to_id: str
    relation: str


def _slugify(title: str) -> str:
    """Filename-safe slug for a title -- lowercase, non-alphanumeric runs collapsed to a
    single hyphen, no leading/trailing hyphen. Not required to be unique on its own (the
    id prefix already guarantees a unique filename); this only needs to keep the filename
    readable and shell-safe."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def _node_path_for_id(node_id: str) -> Optional[Path]:
    if not _SI_DIR.is_dir():
        return None
    for path in _SI_DIR.glob(f"{node_id}_*.md"):
        return path
    return None


def _parse_node_file(path: Path) -> SiNode:
    match = _FILENAME_RE.match(path.name)
    if match is None:
        raise SiFilesError(f"{path}: filename doesn't match NNNN_slug.md")
    node_id = match.group(1)

    text = path.read_text()
    header, _, body = text.partition("\n\n")
    title_match = _HEADER_TITLE_RE.search(header)
    if title_match is None:
        raise SiFilesError(f"{path}: missing 'title:' header line")
    title = title_match.group(1).strip()
    trigger_match = _HEADER_TRIGGER_RE.search(header)
    trigger = trigger_match.group(1).strip() if trigger_match else None
    if trigger == "":
        trigger = None

    return SiNode(id=node_id, title=title, trigger=trigger, body=body, path=path)


def list_nodes() -> list[SiNode]:
    """Every node currently on disk, in filename (id) order. Empty list, not an error, if
    instructions_system/ doesn't exist yet -- mirrors Instruction's own "no rows yet" case
    rather than treating an empty/absent tree as a failure."""
    if not _SI_DIR.is_dir():
        return []
    return [_parse_node_file(path) for path in sorted(_SI_DIR.glob("*.md")) if _FILENAME_RE.match(path.name)]


def next_id() -> str:
    """The next unused NNNN id, one past the highest id currently on disk (0001 if the
    directory is empty) -- ids are never reused after a delete, the same append-only
    convention Instruction.id (an autoincrementing DB primary key) already has, so a
    stale cross-reference to a deleted node fails loudly (file not found) instead of
    silently resolving to whatever new node happens to reuse that id."""
    existing = [int(n.id) for n in list_nodes()]
    next_n = (max(existing) + 1) if existing else 1
    if next_n > 10**_ID_WIDTH - 1:
        raise SiFilesError(f"id space exhausted (next id {next_n} exceeds {_ID_WIDTH} digits)")
    return str(next_n).zfill(_ID_WIDTH)


def load_graph() -> list[SiEdge]:
    if not _GRAPH_PATH.is_file():
        return []
    raw = json.loads(_GRAPH_PATH.read_text())
    return [SiEdge(from_id=e["from"], to_id=e["to"], relation=e["relation"]) for e in raw]


def save_graph(edges: list[SiEdge]) -> None:
    _SI_DIR.mkdir(parents=True, exist_ok=True)
    # Sorted for a stable, low-diff-noise git history -- an edge added anywhere shouldn't
    # reorder every other line the way append-only insertion order would on a rewrite.
    ordered = sorted(edges, key=lambda e: (e.relation, e.from_id, e.to_id))
    _GRAPH_PATH.write_text(
        json.dumps([{"from": e.from_id, "to": e.to_id, "relation": e.relation} for e in ordered], indent=2) + "\n"
    )


def _render_node_file(title: str, trigger: Optional[str], body: str) -> str:
    trigger_line = f"trigger: {trigger}\n" if trigger else ""
    return f"title: {title}\n{trigger_line}\n{body}"


def save_node(node_id: str, title: str, trigger: Optional[str], body: str, *, old_path: Optional[Path] = None) -> Path:
    """Write (create or overwrite) a node's file. If old_path is given and its filename's
    slug no longer matches the new title, the old file is removed after the new one is
    written -- a title edit renames the file (matching id, new slug) rather than leaving a
    stale filename pointing at a node whose title moved on, since the slug exists purely
    for human readability when browsing the directory, not as a second id."""
    _SI_DIR.mkdir(parents=True, exist_ok=True)
    new_path = _SI_DIR / f"{node_id}_{_slugify(title)}.md"
    new_path.write_text(_render_node_file(title, trigger, body))
    if old_path is not None and old_path != new_path and old_path.is_file():
        old_path.unlink()
    return new_path


def delete_node_file(node: SiNode) -> None:
    node.path.unlink()


def resolve(ref: str) -> Optional[SiNode]:
    """Resolve a node reference by id or by title -- mirrors
    kb_cli.instruction._resolve exactly: '#' prefix optional, id checked first, title
    lookup as fallback. Returns None (not an exception) when nothing matches; the CLI
    layer decides what to do with a miss, same division of responsibility as the DB
    version."""
    bare = ref[1:] if ref.startswith("#") else ref
    if bare.isdigit():
        node_id = bare.zfill(_ID_WIDTH)
        path = _node_path_for_id(node_id)
        if path is not None:
            return _parse_node_file(path)
    for node in list_nodes():
        if node.title == ref:
            return node
    return None


def resolve_ref(ref: str) -> Optional[SiNode]:
    """The file-backed counterpart to kb_cli.instruction._resolve_ref -- "root" means the
    tree's one entry point (the node with no incoming parent-of edge), not a literal title
    lookup. Falls through to None if there are zero or more than one such node, same as
    the DB version's handling of a malformed/incomplete tree."""
    if ref == "root":
        roots = [
            n for n in list_nodes() if not any(e.to_id == n.id for e in load_graph() if e.relation == _PARENT_RELATION)
        ]
        return roots[0] if len(roots) == 1 else None
    return resolve(ref)


def children_of(node_id: str) -> list[SiNode]:
    child_ids = {e.to_id for e in load_graph() if e.relation == _PARENT_RELATION and e.from_id == node_id}
    if not child_ids:
        return []
    by_id = {n.id: n for n in list_nodes()}
    return [by_id[cid] for cid in sorted(child_ids) if cid in by_id]


def parent_of(node_id: str) -> Optional[SiNode]:
    edges = [e for e in load_graph() if e.relation == _PARENT_RELATION and e.to_id == node_id]
    if not edges:
        return None
    by_id = {n.id: n for n in list_nodes()}
    return by_id.get(edges[0].from_id)


def set_parent(node_id: str, parent_id: Optional[str]) -> None:
    """Replace node_id's own incoming parent-of edge with one from parent_id (or remove it
    entirely if parent_id is None) -- the file-graph counterpart to
    kb_cli.instruction._set_parent_link. A node has at most one incoming parent-of edge by
    construction here, mirroring the DB version's own documented invariant."""
    edges = [e for e in load_graph() if not (e.relation == _PARENT_RELATION and e.to_id == node_id)]
    if parent_id is not None:
        edges.append(SiEdge(from_id=parent_id, to_id=node_id, relation=_PARENT_RELATION))
    save_graph(edges)


def links_for(node_id: str) -> list[SiEdge]:
    """Every edge touching node_id on either side, any relation -- the file-graph
    counterpart to EntityLink.for_entity, used by a future `kb si show --links`."""
    return [e for e in load_graph() if e.from_id == node_id or e.to_id == node_id]
