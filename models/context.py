"""Context, the tree of places, and Tag, the flat labels a Context carries."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import ForeignKey, Integer, Text, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.columns import HasUniqueName


class Context(Base, HasUniqueName):
    """A GTD-style location/situation node (e.g. "pg" -> "Serbule Hills" -> "Serbule Hills
    Tavern") -- where/with-what an item is actionable. Single-parent tree via parent_id
    (adjacency list): every node has at most one parent, matching the physical reality that
    a place lives in exactly one broader place. See Tag for the orthogonal "what kind of
    place is this" facet (a Context can carry several Tags, e.g. two different taverns both
    tagged "tavern"), which is how a Todo like "buy salt" surfaces under any tavern without
    being pinned to one."""

    __tablename__ = "context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    parent: Mapped[Optional[Context]] = relationship("Context", remote_side=[id])
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary="context_tag")

    @classmethod
    def get_or_create(cls, session: Session, name: str, description: Optional[str] = None) -> Context:
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            obj = cls(name=name, description=description)
            session.add(obj)
            session.flush()
        return obj

    @classmethod
    def create(
        cls, session: Session, name: str, parent: Optional[Context] = None, description: Optional[str] = None
    ) -> Context:
        """A new context, refusing a name already taken (names are unique across deleted rows too)."""
        name = name.strip()
        if not name:
            raise ValueError("context name is empty")
        existing = session.scalars(select(cls).where(cls.name == name)).one_or_none()
        if existing is not None:
            raise ValueError(f"Context {name!r} already exists (#{existing.id})")
        context = cls(name=name, description=description)
        session.add(context)
        context.move_under(parent)
        session.flush()
        return context

    def move_under(self, parent: Optional[Context]) -> None:
        """Re-parent this context (None makes it top-level), refusing any move that would form a cycle."""
        if parent is not None:
            if parent.deleted_at is not None:
                raise ValueError(f"cannot move under deleted context {parent.name!r}")
            if self in parent.ancestors():
                raise ValueError(f"cannot move {self.name!r} under its own descendant {parent.name!r}")
        self.parent = parent

    @classmethod
    def get_existing(cls, session: Session, name: str) -> Context:
        """Look up a context by name, raising if it's missing -- used only where the name is
        known-good already (e.g. self_and_descendants walking an already-resolved Context), never
        on raw user-typed input -- context.py resolves that, with suggestions on a miss."""
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            raise ValueError(f"no such context: {name!r} (create it with: kb context add {name!r})")
        return obj

    def ancestors(self) -> list[Context]:
        """This context plus every parent up the chain, broadest last."""
        chain = [self]
        node = self
        while node.parent is not None:
            node = node.parent
            chain.append(node)
        return chain

    @staticmethod
    def filed_models() -> list[type[Base]]:
        """Every model whose rows are filed in a Context: one with a `context_id` column, one per
        inheritance hierarchy, except the association tables of Context's own many-to-many
        relationships (context_tag is a Context's tags, deleted with it, not a record filed
        there). Read from the mapper registry, so a new model is included with no list to
        update."""
        own_tables = {rel.secondary for rel in inspect(Context).relationships if rel.secondary is not None}
        return sorted(
            (
                mapper.class_
                for mapper in Base.registry.mappers
                if mapper.inherits is None and "context_id" in mapper.columns and mapper.local_table not in own_tables
            ),
            key=lambda model: model.__name__,
        )

    @classmethod
    def self_and_descendants(cls, session: Session, name: str) -> Sequence[Context]:
        """`name` itself plus every context reachable by walking parent_id downward
        (e.g. "pg" matches "pg", "pg"'s children, their children, ...)."""
        root = cls.get_existing(session, name)
        all_contexts = session.scalars(select(cls)).all()
        by_parent: dict[Optional[int], list[Context]] = {}
        for c in all_contexts:
            by_parent.setdefault(c.parent_id, []).append(c)

        result = [root]
        frontier = [root]
        while frontier:
            next_frontier = []
            for node in frontier:
                next_frontier.extend(by_parent.get(node.id, []))
            result.extend(next_frontier)
            frontier = next_frontier
        return result

    @classmethod
    def active_tag_ids(cls, contexts: Sequence[Context]) -> list[int]:
        """Every Tag id carried by any Context in `contexts` (e.g. from
        self_and_descendants) -- the set a tag_id-addressed Goal/Todo/Daily/Idea
        must match to surface under this context subtree. See HasContextOrTag."""
        ids: set[int] = set()
        for c in contexts:
            ids.update(t.id for t in c.tags)
        return list(ids)

    def __repr__(self) -> str:
        parent_str = f" -> {self.parent.name}" if self.parent else ""
        return f"<Context {self.name!r}{parent_str}>"


class Tag(Base, HasUniqueName):
    """A flat, non-hierarchical label for "what kind of place/thing is this"
    (e.g. "tavern") -- orthogonal to Context's tree. A Context can carry several
    Tags (context_tag, many-to-many); Goal/Todo/Daily/Idea can carry at most one
    Tag, mutually exclusive with having a context_id (see each entity's validation).
    A tagged, context-free item (e.g. "buy salt" tagged "tavern") surfaces under
    any active Context whose subtree contains a Context carrying that same Tag,
    without being pinned to one specific place."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    def __repr__(self) -> str:
        return f"<Tag {self.name!r}>"


class ContextTag(Base):
    __tablename__ = "context_tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_id: Mapped[int] = mapped_column(Integer, ForeignKey("context.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag.id"), nullable=False)
