"""Channel/message endpoints backing the web UI's Slack-like chat view -- reuses the same
Channel/ChannelSubscription/ChannelMessage/HarnessSession primitives `kb sessions
send`/`broadcast`/`inbox` already use (see models.py's HarnessSession + Channel messaging
section), so a message sent from the UI and one sent via the CLI are indistinguishable to
every reader on either side.

The UI's sidebar shows one "channel slot" per currently-live agent (a DM) plus the broadcast
channel, without requiring a real Channel row to exist yet -- find_or_create_dm/
get_or_create_named are only called on first send, matching the CLI's own lazy-creation
behavior, so listing channels never creates one no message has been sent into."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from kb_cli.sessions import _BROADCAST_CHANNEL_NAME
from models import Channel, ChannelMessage, ChannelSubscription, HarnessSession

router = APIRouter(prefix="/channels")


class ChannelSummaryOut(BaseModel):
    # channel_id is None when no message has been sent yet -- see Channel.find_dm.
    channel_id: Optional[int]
    kind: str  # "dm" or "broadcast"
    agent_session_id: Optional[str] = None  # set for kind == "dm"
    agent_title: str = ""
    agent_cwd: str = ""
    last_message_at: Optional[str] = None


@router.get("", response_model=list[ChannelSummaryOut])
async def list_channels(display_name: str, session: Session = Depends(get_session)) -> list[ChannelSummaryOut]:
    """One entry per currently-live agent session (a DM slot) plus the broadcast channel --
    scoped to live agents only, per the web UI's "start simple" requirement; a DM with an
    agent that has since exited simply drops out of this list even if history exists (still
    reachable directly via GET /channels/{id}/messages using its old channel_id)."""
    human = HarnessSession.get_or_create_human(session, display_name)
    session.commit()

    summaries = []
    for agent in HarnessSession.live(session):
        dm_channel = Channel.find_dm(session, human.id, agent.id)
        channel_id = dm_channel.id if dm_channel is not None else None
        last_message_at = None
        if channel_id is not None:
            latest = session.scalars(
                select(ChannelMessage).where(ChannelMessage.channel_id == channel_id).order_by(ChannelMessage.id.desc())
            ).first()
            if latest is not None:
                last_message_at = latest.created_at.isoformat()
        summaries.append(
            ChannelSummaryOut(
                channel_id=channel_id,
                kind="dm",
                agent_session_id=agent.id,
                agent_title=agent.title or "",
                agent_cwd=agent.cwd,
                last_message_at=last_message_at,
            )
        )

    broadcast = session.scalars(select(Channel).where(Channel.name == _BROADCAST_CHANNEL_NAME)).first()
    broadcast_last_at = None
    if broadcast is not None:
        latest = session.scalars(
            select(ChannelMessage).where(ChannelMessage.channel_id == broadcast.id).order_by(ChannelMessage.id.desc())
        ).first()
        if latest is not None:
            broadcast_last_at = latest.created_at.isoformat()
    summaries.append(
        ChannelSummaryOut(
            channel_id=broadcast.id if broadcast is not None else None,
            kind="broadcast",
            last_message_at=broadcast_last_at,
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


class SendMessageIn(BaseModel):
    display_name: str
    body: str


class SendToAgentIn(SendMessageIn):
    agent_session_id: str


@router.post("/dm", response_model=ChannelMessageOut)
async def send_dm(payload: SendToAgentIn, session: Session = Depends(get_session)) -> ChannelMessageOut:
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


@router.post("/broadcast", response_model=ChannelMessageOut)
async def send_broadcast(payload: SendMessageIn, session: Session = Depends(get_session)) -> ChannelMessageOut:
    """Posts into the shared "broadcast" Channel -- same channel `kb sessions broadcast`
    posts into, so every currently-subscribed live agent receives it exactly as if the CLI had
    sent it. The human's own HarnessSession is subscribed to the broadcast channel on first
    use here (mirroring cmd_register's auto-subscribe for a new agent session) so future
    GET /channels/{id}/messages history is reachable the same way for a human as an agent."""
    human = HarnessSession.get_or_create_human(session, payload.display_name)
    broadcast = Channel.get_or_create_named(session, _BROADCAST_CHANNEL_NAME)
    ChannelSubscription.subscribe(session, channel_id=broadcast.id, session_id=human.id)
    msg = ChannelMessage.post(session, channel_id=broadcast.id, from_session=human.id, body=payload.body)
    session.commit()
    return ChannelMessageOut(
        id=msg.id,
        from_session=human.id,
        from_title=payload.display_name,
        body=msg.body,
        created_at=msg.created_at.isoformat(),
    )
