"""ArchivedLink, a URL snapshot with the reason it was kept."""

from __future__ import annotations

import enum
import struct
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Enum, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base, UtcDateTime
from models.behaviors.embedding import HasEmbedding
from models.journal.tracking import HasJournal


class ArchivedLinkPushStatus(enum.Enum):
    PENDING = "pending"  # not yet attempted -- fresh row, or startup reconciliation hasn't reached it yet
    QUEUED = "queued"  # background push accepted by the server, not yet resolved
    SUCCESS = "success"  # ab_id confirmed, either via a fresh push or a dedup lookup finding an existing snapshot
    FAILED = "failed"  # push attempted and confirmed failed -- see push_error; only retried via `kb ab retry`


class ArchivedLinkContentStatus(enum.Enum):
    NOT_ATTEMPTED = "not_attempted"  # embedding (if any) covers title+reason only, content never fetched
    EMBEDDED = "embedded"  # content was fetched and folded into the embedding
    FETCH_FAILED = "fetch_failed"  # content fetch was attempted and failed -- see content_fetch_error, `kb ab pull`


class ArchivedLink(Base, HasEmbedding, HasJournal):
    """A URL queued for archival -- interim capture ahead of a live ArchiveBox instance
    (kb Goal/Todo #70). Today this is just url+title+reason+timestamp; migrated_at marks
    the row as already pushed into a real ArchiveBox once that integration exists, so the
    same table can be replayed against it without re-deciding what's already been sent.
    title and reason are two different axes, both required: title is a neutral description
    of what the page/content actually is (what a fetch against a live ArchiveBox would want
    to auto-fill from the page's own <title>, when a page's own title is generic or missing
    context, override it by hand rather than saving the bare auto-title); reason is why it
    was worth keeping -- what made it pass the filter, what task/question led to finding it.
    Neither is optional -- the point is to never save a bare URL with no record of what it is
    or why it mattered, the same way a link shared with a person should come with why the
    sender thought it mattered rather than dumping the burden of figuring that out on the
    reader later.
    Each row's id is cited elsewhere in kb as ABn (e.g. "AB23") -- embed that token in any
    Note/Todo/Journal body that references the URL, so the pointer travels with the prose
    instead of living only in this table. ABn today means this table's own id; once a live
    ArchiveBox instance exists, migrated ids get remapped to the real AB snapshot id and
    every ABn citation in kb text is updated to match.

    push_status tracks the live-ArchiveBox push independently of ab_id/push_error being
    populated, so "is this row still owed attention" is one column, not an inference over two
    others: PENDING (fresh, no push attempted yet) -> QUEUED (kb.service accepted the
    background job) -> SUCCESS or FAILED (resolved, either by a successful push or a dedup
    lookup that found the URL already archived). resolved_at is set only on that final
    transition -- when the row's fate became known, not when a push merely started. A row
    stuck at PENDING/QUEUED across a kb.service restart is exactly what startup reconciliation
    (server.py's lifespan) looks for and logs -- see kb Note #105 and kb Todo #70."""

    __tablename__ = "archived_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    migrated_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    ab_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    push_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    push_status: Mapped[ArchivedLinkPushStatus] = mapped_column(
        Enum(ArchivedLinkPushStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=ArchivedLinkPushStatus.PENDING,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    content_status: Mapped[ArchivedLinkContentStatus] = mapped_column(
        Enum(ArchivedLinkContentStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=ArchivedLinkContentStatus.NOT_ATTEMPTED,
    )
    content_fetch_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "reason"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.reason}"

    def reembed_with_content(self, content: str) -> None:
        """The one place content gets folded into the embedding. `content` is a plain function
        argument, never assigned to any attribute (mapped or otherwise) on self, so it never
        reaches the DB and never lingers on the instance -- kb's DB stays limited to
        user-written content plus small derived vectors, never bulk page text (see kb Note
        #162). Deliberately bypasses the base HasEmbedding.reembed()/_embed_source_text() path
        (which takes no arguments and is driven by the before_flush listener off _embed_fields()
        alone) since content-aware embedding is always an explicit, caller-initiated action, not
        something a plain title/reason attribute change should ever trigger. Caller is
        responsible for content_status/content_fetch_error bookkeeping around this call (see
        kb_cli/archivebox.py's fetch_and_embed_content(), the shared function both the
        push-queue worker and `kb ab backfill-content` call)."""
        from embed import embed, model_name

        vec = embed(f"{self.title}\n\n{self.reason}\n\n{content}")
        self.embedding = struct.pack(f"{len(vec)}f", *vec)
        self.embedding_model = model_name()

    @classmethod
    def create(cls, session: Session, url: str, title: str, reason: str) -> ArchivedLink:
        link = cls(url=url, title=title, reason=reason)
        link.reembed()
        session.add(link)
        session.flush()
        return link

    @classmethod
    def needing_content_backfill(cls, session: Session) -> Sequence[ArchivedLink]:
        """SUCCESS-pushed rows whose embedding still only covers title+reason and haven't
        already been recorded as a permanent content-fetch failure -- the exact candidate set
        `kb ab backfill-content` (and the push-queue worker, per-row) operates on. Excluding
        FETCH_FAILED here is what keeps a broken snapshot (e.g. singlefile.html missing) from
        being re-attempted on every single backfill run forever -- `kb ab retry`/`kb ab pull`
        followed by a manual re-embed is the deliberate escape hatch once ArchiveBox actually
        has the content."""
        return session.scalars(
            select(cls)
            .where(cls.push_status == ArchivedLinkPushStatus.SUCCESS)
            .where(cls.content_status == ArchivedLinkContentStatus.NOT_ATTEMPTED)
            .order_by(cls.created_at)
        ).all()

    @classmethod
    def find_by_url(cls, session: Session, url: str) -> Optional[ArchivedLink]:
        return session.scalars(select(cls).where(cls.url == url).order_by(cls.created_at)).first()

    @classmethod
    def pending(cls, session: Session) -> Sequence[ArchivedLink]:
        return session.scalars(select(cls).where(cls.migrated_at.is_(None)).order_by(cls.created_at)).all()

    @classmethod
    def stuck_mid_push(cls, session: Session) -> Sequence[ArchivedLink]:
        """Rows still PENDING/QUEUED -- either never picked up, or mid-flight when kb.service
        last stopped. Startup reconciliation (server.py's lifespan) is the one caller."""
        return session.scalars(
            select(cls)
            .where(cls.push_status.in_((ArchivedLinkPushStatus.PENDING, ArchivedLinkPushStatus.QUEUED)))
            .order_by(cls.created_at)
        ).all()

    def __repr__(self) -> str:
        state = "migrated" if self.migrated_at else "pending"
        return f"<ArchivedLink #{self.id} [{state}] {self.title!r} {self.url}>"
