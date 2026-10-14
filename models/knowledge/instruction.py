"""Instruction, a node of the guidance tree."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal
from models.links.entity_link import EntityLink


class Instruction(Base, HasContextOrTag, HasEmbedding, HasJournal):
    """A node in the graph of durable guidance -- unifies what would otherwise be scattered
    across CLAUDE.md files, Claude Code skills, and Claude Code memory into one structure. Tree
    structure (topic parent/child, e.g. "engineering" -> "react" -> "dnd-kit") is expressed as
    ordinary EntityLink rows with relation "parent-of" (a --parent-of--> b means a is the parent
    of b), not a parent_id column -- the same graph mechanism every other kb entity already uses
    for cross-references (see EntityLink), so Instruction has one graph mechanism, not two. This
    is a SEPARATE graph from Context's own tree: Context is where something is actionable (e.g.
    "pg" -> "Serbule Hills Tavern"); Instruction's parent-of graph is what topic something belongs
    to, independent of place. A node can optionally also carry a context_id/tag_id (via
    HasContextOrTag) to link it into the Context tree when it's genuinely tied to a place, not
    just a topic (e.g. NPC lore that should surface automatically when Context walks into that
    location). A node may also carry arbitrary non-hierarchical EntityLinks to any other node
    (another Instruction, or a Note/Goal/Todo/etc.) via any other relation label -- roots()/
    children() only ever look at "parent-of" edges, the rest of the graph is free-form.

    trigger is required on every node (enforced by `kb i add`, even a null-DB value on old rows is a
    retrofit gap, not a valid state to create new): it's the short condition shown in a parent's
    children listing that lets an agent decide whether to bother fetching this node's full body at
    all, without reading the body first. A node whose relevance genuinely can't be narrowed still
    gets a trigger -- even a couple words ("engineering work in general") beats none, because an
    unstated trigger is exactly the gap that let nodes go unread: a session skips a child it can't
    yet tell is relevant, and a body-only node gives it nothing to make that call with. There is no
    separate "trigger tree" -- a trigger-worded node's children ARE topic-tree navigation, just
    phrased as conditions ("whenever doing a merge") instead of topic names ("merge").

    write_globs is the machine-checkable part of a trigger: space-separated globs (`*.py`,
    `*/AGENTS.md`) naming files an agent session must not write until it has read this node. The
    `required-reading-check` hook blocks such a write and names the unread nodes; see
    kb_cli/required_reading.py. Empty means the node gates no file.

    Intended navigation is root-to-leaf, one level at a time, judgment-based (which of this level's
    handful of children is obviously relevant), not a search/similarity operation -- keep each node's
    children few enough (~5-10) that this stays cheap; restructure (insert an intermediate node)
    rather than letting any level's fanout grow past that. See kb Goal #23 for full design rationale,
    and kb Todo #127 for the parent_id -> EntityLink graph migration rationale specifically.

    This is the one table meant for shareable, git-trackable export (a design in progress as of
    2026-07 -- see Goal #23) -- unlike Note (a personal notebook), Instruction's content is
    operational reference documentation, genuinely useful to someone else running this system."""

    __tablename__ = "instruction"
    # Guidance is often universal; a context/tag is an optional narrowing, not a home.
    _context_or_tag_required = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_globs: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional["Tag"]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "body"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.body}"

    _PARENT_RELATION = "parent-of"

    @classmethod
    def roots(cls, session: Session) -> Sequence[Instruction]:
        """Top-level nodes -- no incoming "parent-of" EntityLink -- the entry points to the tree."""
        has_parent_ids = {
            link.id_b
            for link in session.scalars(
                select(EntityLink).where(
                    EntityLink.type_b == "Instruction", EntityLink.relation == cls._PARENT_RELATION
                )
            ).all()
        }
        all_nodes = session.scalars(select(cls)).all()
        return [n for n in all_nodes if n.id not in has_parent_ids]

    @classmethod
    def children(cls, session: Session, parent_id: int) -> Sequence[Instruction]:
        """Direct children of a node (b-side of that node's own "parent-of" EntityLinks), for
        one level of tree expansion."""
        child_ids = [
            link.id_b
            for link in session.scalars(
                select(EntityLink).where(
                    EntityLink.type_a == "Instruction",
                    EntityLink.id_a == parent_id,
                    EntityLink.relation == cls._PARENT_RELATION,
                )
            ).all()
        ]
        if not child_ids:
            return []
        return session.scalars(select(cls).where(cls.id.in_(child_ids))).all()

    @classmethod
    def parent(cls, session: Session, node_id: int) -> Optional[Instruction]:
        """This node's parent, if any -- the a-side of its own incoming "parent-of" EntityLink.
        A node should have at most one; if data ever ends up with more (nothing in the schema
        prevents it, unlike the old parent_id FK), this returns the first and is the one place
        that would need fixing if that invariant is ever enforced more strictly."""
        link = session.scalars(
            select(EntityLink).where(
                EntityLink.type_b == "Instruction",
                EntityLink.id_b == node_id,
                EntityLink.relation == cls._PARENT_RELATION,
            )
        ).first()
        if link is None:
            return None
        return session.get(cls, link.id_a)

    def __repr__(self) -> str:
        trigger_note = f" trigger={self.trigger!r}" if self.trigger else ""
        return f"<Instruction #{self.id} {self.title!r}{trigger_note}{self.age_marker()}>"
