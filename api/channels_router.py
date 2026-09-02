"""Channel/message endpoints backing the web UI's Slack-like chat view -- reuses the same
Channel/ChannelSubscription/ChannelMessage/HarnessSession primitives `kb sessions
send`/`broadcast`/`inbox` already use (see models.py's HarnessSession + Channel messaging
section), so a message sent from the UI and one sent via the CLI are indistinguishable to
every reader on either side.

Scope, deliberately: read/post to channels that already exist (a live agent's DM slot, plus
every named Channel already in the DB -- "broadcast" today, others as agents/CLI usage create
them organically). No channel-creation or subscription-management endpoint yet -- there is no
mechanism today for encouraging/requiring an agent to subscribe to a channel, so building UI
to manage membership would manage a roster nothing else respects. That's future work, tracked
separately, not a gap to paper over here."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from kb_cli.sessions import refresh_agent_title
from models import Channel, ChannelMessage, ChannelSubscription, HarnessSession

router = APIRouter(prefix="/channels")


def _latest_message_at(session: Session, channel_id: int) -> Optional[str]:
    latest = session.scalars(
        select(ChannelMessage).where(ChannelMessage.channel_id == channel_id).order_by(ChannelMessage.id.desc())
    ).first()
    return latest.created_at.isoformat() if latest is not None else None


class ChannelSummaryOut(BaseModel):
    # channel_id is None only for a "dm" slot with no message sent yet -- see Channel.find_dm.
    # A "named" entry always has a real, already-existing channel_id (this endpoint doesn't
    # create channels).
    channel_id: Optional[int]
    kind: str  # "dm" or "named"
    name: Optional[str] = None  # set for kind == "named" (e.g. "broadcast")
    agent_session_id: Optional[str] = None  # set for kind == "dm"
    agent_title: str = ""
    agent_cwd: str = ""
    last_message_at: Optional[str] = None


@router.get("", response_model=list[ChannelSummaryOut])
async def list_channels(display_name: str, session: Session = Depends(get_session)) -> list[ChannelSummaryOut]:
    """One entry per currently-live agent session (a DM slot, kind="dm") plus one entry per
    named Channel that already exists in the DB (kind="named") -- scoped to live agents for
    DMs per the web UI's "start simple" requirement; a DM with an agent that has since exited
    simply drops out of this list even if history exists (still reachable directly via
    GET /channels/{id}/messages using its old channel_id). Named channels are listed
    regardless of the human's own subscription state -- read/post access here isn't gated on
    ChannelSubscription, since there's no membership-management UI yet for a human to have
    joined one through in the first place (see this module's own docstring)."""
    human = HarnessSession.get_or_create_human(session, display_name)
    session.commit()

    summaries = []
    for agent in HarnessSession.live(session):
        refresh_agent_title(session, agent)
        dm_channel = Channel.find_dm(session, human.id, agent.id)
        channel_id = dm_channel.id if dm_channel is not None else None
        summaries.append(
            ChannelSummaryOut(
                channel_id=channel_id,
                kind="dm",
                agent_session_id=agent.id,
                agent_title=agent.title or "",
                agent_cwd=agent.cwd,
                last_message_at=_latest_message_at(session, channel_id) if channel_id is not None else None,
            )
        )

    session.commit()

    named_channels = session.scalars(select(Channel).where(Channel.name.isnot(None)).order_by(Channel.name)).all()
    for channel in named_channels:
        summaries.append(
            ChannelSummaryOut(
                channel_id=channel.id,
                kind="named",
                name=channel.name,
                last_message_at=_latest_message_at(session, channel.id),
            )
        )
    return summaries


class ChannelMessageOut(BaseModel):
    id: int
    from_session: str
    from_title: str
    body: str
    created_at: str


@router.get("/{channel_id}/messages", response_model=list[ChannelMessageOut])
async def get_channel_messages(
    channel_id: int, before_id: Optional[int] = None, limit: int = 50, session: Session = Depends(get_session)
) -> list[ChannelMessageOut]:
    """Newest-first page of a channel's full history (every sender included) -- pass the
    oldest-loaded message's id as before_id to scroll-load further back. See
    ChannelMessage.history's own docstring for why this is a distinct query from
    ChannelMessage.unread rather than a variant of it."""
    if session.get(Channel, channel_id) is None:
        raise HTTPException(status_code=404, detail=f"No channel with id {channel_id}")
    messages = ChannelMessage.history(session, channel_id, before_id=before_id, limit=limit)
    senders = {
        row.id: row
        for row in session.scalars(
            select(HarnessSession).where(HarnessSession.id.in_({m.from_session for m in messages}))
        )
    }
    return [
        ChannelMessageOut(
            id=m.id,
            from_session=m.from_session,
            from_title=(
                (senders[m.from_session].title or m.from_session) if m.from_session in senders else m.from_session
            ),
            body=m.body,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


class SendDmIn(BaseModel):
    display_name: str
    agent_session_id: str
    body: str


@router.post("/dm", response_model=ChannelMessageOut)
async def send_dm(payload: SendDmIn, session: Session = Depends(get_session)) -> ChannelMessageOut:
    """Sends as a human -- creates the human's own HarnessSession row and the DM channel on
    first use, exactly like `kb sessions send` does for an agent-to-agent DM. agent_session_id
    is not required to currently be live: sending to a DM slot that was live when the sidebar
    loaded but has since exited still succeeds, matching cmd_send's own "not blocked" behavior
    for a no-longer-live recipient."""
    human = HarnessSession.get_or_create_human(session, payload.display_name)
    agent = session.get(HarnessSession, payload.agent_session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"No session with id {payload.agent_session_id!r}")
    channel = Channel.find_or_create_dm(session, human.id, agent.id)
    msg = ChannelMessage.post(session, channel_id=channel.id, from_session=human.id, body=payload.body)
    session.commit()
    return ChannelMessageOut(
        id=msg.id,
        from_session=human.id,
        from_title=payload.display_name,
        body=msg.body,
        created_at=msg.created_at.isoformat(),
    )


class SendNamedIn(BaseModel):
    display_name: str
    body: str


@router.post("/named/{channel_name}", response_model=ChannelMessageOut)
async def send_to_named_channel(
    channel_name: str, payload: SendNamedIn, session: Session = Depends(get_session)
) -> ChannelMessageOut:
    """Posts into an already-existing named Channel (e.g. "broadcast") -- same channel `kb
    sessions broadcast`/a future `kb sessions send --channel NAME` would post into, so every
    currently-subscribed live agent receives it exactly as if the CLI had sent it. Refuses a
    channel name with no existing Channel row rather than creating one -- see this module's
    own docstring for why channel creation isn't exposed here yet. The human's own
    HarnessSession is subscribed on first use (mirroring cmd_register's auto-subscribe for a
    new agent session) so future GET /channels/{id}/messages history is reachable the same
    way for a human as an agent."""
    channel = session.scalars(select(Channel).where(Channel.name == channel_name)).first()
    if channel is None:
        raise HTTPException(status_code=404, detail=f"No channel named {channel_name!r}")
    human = HarnessSession.get_or_create_human(session, payload.display_name)
    ChannelSubscription.subscribe(session, channel_id=channel.id, session_id=human.id)
    msg = ChannelMessage.post(session, channel_id=channel.id, from_session=human.id, body=payload.body)
    session.commit()
    return ChannelMessageOut(
        id=msg.id,
        from_session=human.id,
        from_title=payload.display_name,
        body=msg.body,
        created_at=msg.created_at.isoformat(),
    )
