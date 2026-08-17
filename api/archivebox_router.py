"""ArchiveBox push endpoint -- accepts a push request, resolves it on FastAPI's own
BackgroundTasks mechanism so `kb ab add` returns immediately instead of blocking on
ArchiveBox's ~15-20s synchronous add (see kb Note #105). resolve_or_push (kb_cli/archivebox.py)
is the one function that actually talks to ArchiveBox; this router only queues it and reports
whether a link_id is valid up front. Once a push resolves to SUCCESS, this same background task
also fetches and embeds the article content (fetch_and_embed_content) -- so `kb ab add` alone is
enough to get a fully content-searchable row with no separate manual step, matching every other
push-resolution bookkeeping this router already does in one place."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from kb_cli.archivebox import fetch_and_embed_content, resolve_or_push
from models import ArchivedLink, ArchivedLinkPushStatus, SessionFactory

router = APIRouter(prefix="/ab")


class PushIn(BaseModel):
    link_id: int


class PushOut(BaseModel):
    status: str


def _push_in_background(link_id: int) -> None:
    """Runs after the response is sent, in a fresh session -- the request-scoped session from
    the endpoint itself is closed by the time this executes."""
    with SessionFactory() as session:
        link = session.get(ArchivedLink, link_id)
        if link is None:
            return
        resolve_or_push(session, link)
        if link.push_status == ArchivedLinkPushStatus.SUCCESS:
            fetch_and_embed_content(session, link)


@router.post("/push", response_model=PushOut)
async def push(body: PushIn, background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> PushOut:
    link = session.get(ArchivedLink, body.link_id)
    if link is None:
        raise HTTPException(status_code=404, detail=f"ArchivedLink {body.link_id} not found")
    link.push_status = ArchivedLinkPushStatus.QUEUED
    session.commit()
    background_tasks.add_task(_push_in_background, body.link_id)
    return PushOut(status="queued")
