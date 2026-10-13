"""Channels: cross-session messaging between harness sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, and_, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.agents.harness_session import HarnessSession
from models.base import Base, UtcDateTime, _now


class Channel(Base):
    """The one messaging primitive underneath every shape `kb sessions` exposes -- a DM, the
    broadcast channel, and a future named topic channel (`#synth`, `#kb`) are all just a
    Channel with a different name/membership, not three separate mechanisms. name is None for
    a DM (identity is its two-member subscriber set, found via find_or_create_dm, never a
    name), or a real unique string ("broadcast", "synth", ...) for anything else -- created on
    first subscribe with no separate registration step (IRC's model), see get_or_create_named.
    """

    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)

    @classmethod
    def get_or_create_named(cls, session: Session, name: str) -> Channel:
        existing = session.scalars(select(cls).where(cls.name == name)).first()
        if existing is not None:
            return existing
        row = cls(name=name)
        session.add(row)
        session.flush()
        return row

    @classmethod
    def find_dm(cls, session: Session, a: int, b: int) -> Optional[Channel]:
        """A DM is a nameless Channel whose subscriber set is exactly {a, b} -- found by
        looking for a nameless channel both are subscribed to with no third subscriber, not by
        any stored pairing key, since ChannelSubscription is already the one source of truth
        for membership. Read-only: returns None if no such channel exists yet, the one query
        both find_or_create_dm (below) and a read-only "does this DM exist" caller (e.g. the
        web UI listing channels without creating one just by looking) need to share."""
        candidates = session.scalars(
            select(cls.id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == cls.id)
            .where(cls.name.is_(None), ChannelSubscription.session_id.in_([a, b]))
            .group_by(cls.id)
            .having(func.count(func.distinct(ChannelSubscription.session_id)) == 2)
        ).all()
        for channel_id in candidates:
            total = session.scalar(select(func.count()).where(ChannelSubscription.channel_id == channel_id))
            if total == 2:
                return session.get(cls, channel_id)
        return None

    @classmethod
    def find_or_create_dm(cls, session: Session, a: int, b: int) -> Channel:
        """Creates the channel and subscribes both sessions if find_dm finds none yet."""
        existing = cls.find_dm(session, a, b)
        if existing is not None:
            return existing
        row = cls(name=None)
        session.add(row)
        session.flush()
        ChannelSubscription.subscribe(session, channel_id=row.id, session_id=a)
        ChannelSubscription.subscribe(session, channel_id=row.id, session_id=b)
        return row

    def __repr__(self) -> str:
        return f"<Channel #{self.id} {self.name or '(dm)'}>"


class ChannelSubscription(Base):
    """Live/derived channel membership -- a row here plus HarnessSession.is_alive() is the
    entire definition of "currently in this channel," there is no separate durable roster
    concept. subscribed_at is also the lower bound for how far back a newly-joined session can
    see (a named channel's history before you joined isn't backfilled -- see Channel.unread's
    subscribed_at bound); for a DM both members are subscribed at creation, so that bound is
    moot there but doesn't need special-casing."""

    __tablename__ = "channel_subscription"
    __table_args__ = (UniqueConstraint("channel_id", "session_id", name="uq_channel_subscription"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("harness_session.id"), nullable=False)
    subscribed_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)

    @classmethod
    def subscribe(cls, session: Session, channel_id: int, session_id: int) -> ChannelSubscription:
        existing = session.scalars(
            select(cls).where(cls.channel_id == channel_id, cls.session_id == session_id)
        ).first()
        if existing is not None:
            return existing
        row = cls(channel_id=channel_id, session_id=session_id)
        session.add(row)
        session.flush()
        return row


class ChannelMessage(Base):
    """One posted message. id is the delivery offset/cursor value (plain autoincrement PK) --
    ChannelRead.up_to_message_id points at one of these directly, no separate sequence needed.
    No to_session field at all, unlike the old SessionMessage: a message belongs to a channel,
    full stop, and who receives it falls out of ChannelSubscription rather than being baked
    into the message row itself -- this is what makes a DM, a broadcast, and a named channel
    the same table."""

    __tablename__ = "channel_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    from_session: Mapped[int] = mapped_column(Integer, ForeignKey("harness_session.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    sender: Mapped[HarnessSession] = relationship("HarnessSession")

    @classmethod
    def post(cls, session: Session, channel_id: int, from_session: int, body: str) -> ChannelMessage:
        msg = cls(channel_id=channel_id, from_session=from_session, body=body)
        session.add(msg)
        session.flush()
        return msg

    @classmethod
    def history(
        cls, session: Session, channel_id: int, before_id: Optional[int] = None, limit: int = 50
    ) -> list[ChannelMessage]:
        """One page of a channel's full message history, newest-first, every sender included
        (unlike unread(), which excludes the caller's own messages and is scoped to what one
        session hasn't read yet) -- backs the web UI's scroll-load-older channel view, where
        "who sent it" is a thing to display, not a thing to filter by. before_id (an id from
        the oldest message already loaded) pages further back; omitted, this is the most
        recent `limit` messages in the channel."""
        q = select(cls).where(cls.channel_id == channel_id)
        if before_id is not None:
            q = q.where(cls.id < before_id)
        rows = session.scalars(q.order_by(cls.id.desc()).limit(limit)).all()
        return list(rows)

    @classmethod
    def unread(cls, session: Session, session_id: int, channel_id: Optional[int] = None) -> Sequence[ChannelMessage]:
        """Messages in channels session_id is subscribed to, with id greater than that
        session's own read cursor for that channel (MAX(up_to_message_id) across its
        ChannelRead rows for the channel, or 0/all if it has never read that channel), bounded
        below by ChannelSubscription.subscribed_at so a session never sees a named channel's
        history from before it joined -- moot for a DM (both members subscribed at creation)
        but applies unconditionally rather than special-casing DMs out of it. channel_id
        narrows to one channel (e.g. cmd_send's own DM); omitted, this is every subscribed
        channel at once (cmd_inbox/cmd_listen's own use)."""
        sub_rows = session.execute(
            select(ChannelSubscription.channel_id, ChannelSubscription.subscribed_at).where(
                ChannelSubscription.session_id == session_id
            )
        ).all()
        subs: list[tuple[int, datetime]] = [(cid, sub_at) for cid, sub_at in sub_rows]
        if channel_id is not None:
            subs = [(cid, sub_at) for cid, sub_at in subs if cid == channel_id]
        if not subs:
            return []
        cursor_rows = session.execute(
            select(ChannelRead.channel_id, func.max(ChannelRead.up_to_message_id))
            .where(ChannelRead.session_id == session_id)
            .group_by(ChannelRead.channel_id)
        ).all()
        cursors: dict[int, int] = {cid: max_id for cid, max_id in cursor_rows}
        clauses = []
        for cid, subscribed_at in subs:
            cursor = cursors.get(cid, 0)
            clauses.append(and_(cls.channel_id == cid, cls.id > cursor, cls.created_at >= subscribed_at))
        return session.scalars(
            select(cls).where(or_(*clauses), cls.from_session != session_id).order_by(cls.created_at)
        ).all()

    def __repr__(self) -> str:
        return f"<ChannelMessage #{self.id} channel={self.channel_id} from={self.sender.harness_id}>"


class ChannelRead(Base):
    """One row per read *event* (one `kb sessions inbox`/`listen` call that found unread
    mail), never one row per message -- a session's read cursor for a channel is
    MAX(up_to_message_id) across its own rows here for that channel. Deliberately append-only
    rather than a single upserted cursor: keeps the actual history of when a session checked
    and what it saw as current, so a later consistency check can walk a session's read-event
    sequence per channel and confirm up_to_message_id never skips/lags behind the channel's
    real max message id at that time -- not built yet, but this table's shape is what makes it
    buildable. record() always computes the true current max, never a stale/approximate value,
    which is the one invariant that has to hold for such a check to mean anything."""

    __tablename__ = "channel_read"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("harness_session.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    up_to_message_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel_message.id"), nullable=False)

    @classmethod
    def record(cls, session: Session, channel_id: int, session_id: int) -> Optional[ChannelRead]:
        """Writes one ChannelRead row pinned to the channel's true current max message id.
        Returns None (writes nothing) if the channel has no messages at all yet -- there is no
        meaningful up_to_message_id to record."""
        max_id = session.scalar(select(func.max(ChannelMessage.id)).where(ChannelMessage.channel_id == channel_id))
        if max_id is None:
            return None
        row = cls(channel_id=channel_id, session_id=session_id, up_to_message_id=max_id)
        session.add(row)
        session.flush()
        return row
