"""EntityLink, a typed relation between any two records."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy import Integer, String, Text, UniqueConstraint, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base


class EntityLink(Base):
    """Untyped graph edge between any two rows in any mapped table (Goal, Todo, Note, ...),
    addressed the same polymorphic way Journal addresses its target: a type name (the mapped
    class's own __name__, see entity_registry()) plus that row's integer id. There is no
    DB-level FK to either side -- SQLite/Postgres have no construct for "FK to whichever
    table type_a names" -- so referential integrity is enforced once, in create(), by looking
    the id up against entity_registry()[type] before the row is ever written; nothing later (traversal, deletion
    elsewhere in the codebase) re-checks it.

    a/b are stored in caller-given order, not canonicalized -- `relation` is a free-text
    label that reads a-to-b (e.g. "tracked-by" means a is tracked by b), so an earlier version
    that sorted (type_a, id_a, type_b, id_b) into one canonical order before insert silently
    flipped the meaning of any asymmetric relation whenever the caller's argument order
    differed from (type, id) sort order -- e.g. create("Note", 98, "Note", 97, "found-during")
    got stored as "Note:97 found-during Note:98", the reverse of what was actually meant. The
    UniqueConstraint below only catches an exact-order duplicate; create(A, B, rel) and
    create(B, A, rel) are treated as two different (probably one of them mistaken) facts, not
    the same fact in two spellings -- deliberately, since there's no way to know a relation is
    symmetric from a plain string.
    """

    __tablename__ = "entity_link"
    __table_args__ = (UniqueConstraint("type_a", "id_a", "type_b", "id_b", "relation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_a: Mapped[str] = mapped_column(String, nullable=False)
    id_a: Mapped[int] = mapped_column(Integer, nullable=False)
    type_b: Mapped[str] = mapped_column(String, nullable=False)
    id_b: Mapped[int] = mapped_column(Integer, nullable=False)
    relation: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def entity_registry() -> dict[str, type[Base]]:
        """Every mapped class, live from SQLAlchemy's own declarative registry (shared across
        all Base subclasses) -- not a hand-maintained dict, so a new model
        becomes linkable automatically, with nothing here to remember to update."""
        return {m.class_.__name__: m.class_ for m in Base.registry.mappers}

    @classmethod
    def resolve(cls, session: Session, entity_type: str, entity_id: int) -> Any:
        """The row (type, id) actually points at, or None if entity_type is unknown or no such
        row exists -- the one validation this whole table's integrity rests on."""
        model = cls.entity_registry().get(entity_type)
        if model is None:
            return None
        return session.get(model, entity_id)

    @classmethod
    def create(
        cls,
        session: Session,
        type_a: str,
        id_a: int,
        type_b: str,
        id_b: int,
        relation: str,
        note: Optional[str] = None,
    ) -> EntityLink:
        """Validates both endpoints exist (raises ValueError naming the missing side). Stores
        a/b in exactly the order passed -- relation reads a-to-b, so the caller's order is
        meaningful and is never reordered (see class docstring)."""
        if cls.resolve(session, type_a, id_a) is None:
            raise ValueError(f"{type_a}:{id_a} does not exist")
        if cls.resolve(session, type_b, id_b) is None:
            raise ValueError(f"{type_b}:{id_b} does not exist")
        link = cls(type_a=type_a, id_a=id_a, type_b=type_b, id_b=id_b, relation=relation, note=note)
        session.add(link)
        session.flush()
        return link

    @classmethod
    def for_entity(cls, session: Session, entity_type: str, entity_id: int) -> Sequence[EntityLink]:
        """Every link touching (entity_type, entity_id) on either side -- the one query both
        `kb link show` traversal and a delete-guard's "what's blocking this" check use."""
        return session.scalars(
            select(cls)
            .where(
                or_(
                    (cls.type_a == entity_type) & (cls.id_a == entity_id),
                    (cls.type_b == entity_type) & (cls.id_b == entity_id),
                )
            )
            .order_by(cls.relation, cls.type_a, cls.id_a, cls.type_b, cls.id_b)
        ).all()

    def other_side(self, entity_type: str, entity_id: int) -> tuple[str, int]:
        """Given one endpoint of this link, the (type, id) of the other endpoint."""
        if (self.type_a, self.id_a) == (entity_type, entity_id):
            return (self.type_b, self.id_b)
        return (self.type_a, self.id_a)

    def __repr__(self) -> str:
        return f"<EntityLink #{self.id} {self.type_a}:{self.id_a} --{self.relation}--> {self.type_b}:{self.id_b}>"
