"""Note, durable reference knowledge."""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.context import Context
from models.journal.tracking import HasJournal
from models.links.auto_links import HasAutoLinks


class Collection(enum.Enum):
    ENGINEERING = "engineering"
    PERSONAL = "personal"
    WORK = "work"
    INBOX = "inbox"  # default collection for a note created without an explicit one

    ALL = "all"  # search-only sentinel — not a valid storage collection


_STORAGE_COLLECTIONS = {c for c in Collection if c != Collection.ALL}


class Note(Base, HasEmbedding, HasAutoLinks, HasJournal):
    """A personal knowledge base / lab notebook entry -- durable facts worth keeping because
    they were useful or interesting to this user, with no claim of being fact-checked, curated,
    or written for an audience. Deliberately NOT designed for shareable/git-tracked export the
    way Instruction is -- see kb Goal #23's Journal for the reasoning (Instruction is reference
    documentation, meant for an audience; Note is a personal notebook, correctness bar is
    "good enough for me")."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    collection: Mapped[Collection] = mapped_column(
        Enum(Collection, create_constraint=True, validate_strings=True), nullable=False
    )
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # comma-separated
    # Where the note belongs (a project, a pet, a place), on the same Context tree as
    # Todo/Goal -- orthogonal to `collection`, which says what kind of note it is.
    context_id: Mapped[int] = mapped_column(Integer, ForeignKey("context.id"), nullable=False)
    context: Mapped[Context] = relationship("Context")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "body"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.body}"

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        body: str,
        context: Context,
        collection: Collection = Collection.INBOX,
        tags: Optional[str] = None,
    ) -> Note:
        if collection == Collection.ALL:
            raise ValueError("Collection.ALL is a search sentinel and cannot be used for storage.")
        note = cls(title=title, body=body, collection=collection, tags=tags, context=context)
        note.reembed()
        session.add(note)
        session.flush()
        return note

    @classmethod
    def get(cls, session: Session, id: int) -> Optional[Note]:
        return session.scalars(select(cls).filter_by(id=id)).one_or_none()

    @classmethod
    def find(cls, session: Session, title: str) -> Optional[Note]:
        return session.scalars(select(cls).filter_by(title=title)).one_or_none()

    def update(
        self,
        title: Optional[str] = None,
        body: Optional[str] = None,
        tags: Optional[str] = None,
        collection: Optional[Collection] = None,
    ) -> None:
        if title is not None:
            self.title = title
        if body is not None:
            self.body = body
        if tags is not None:
            self.tags = tags
        if collection is not None:
            if collection == Collection.ALL:
                raise ValueError("Collection.ALL is a search sentinel and cannot be used for storage.")
            self.collection = collection

    def __repr__(self) -> str:
        tags_str = f" #{self.tags}" if self.tags else ""
        return f"<Note #{self.id} {self.collection.value}/{self.title!r}{tags_str} [{self.context.name}]{self.age_marker()}>"
