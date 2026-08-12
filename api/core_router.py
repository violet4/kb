"""Core endpoints: embedding + Note semantic search/create/update. This is the
HTTP replacement for the old hand-rolled Unix-socket protocol in server.py --
same operations, plain REST instead of a bespoke newline-JSON framing, so any
HTTP-capable caller (client.py, the future frontend, curl) speaks one shared
interface."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from embed import _local_embed as embed, model_name
from models import Collection, Note

router = APIRouter()


class PingOut(BaseModel):
    result: str


@router.get("/ping", response_model=PingOut)
async def ping() -> PingOut:
    return PingOut(result=f"pong model={model_name()}")


class EmbedIn(BaseModel):
    text: str


class EmbedOut(BaseModel):
    result: list[float]


@router.post("/embed", response_model=EmbedOut)
async def embed_text(body: EmbedIn) -> EmbedOut:
    return EmbedOut(result=embed(body.text))


class NoteSearchResult(BaseModel):
    id: int
    title: str
    body: str
    collection: str
    tags: Optional[str]
    dist: float


@router.get("/search", response_model=list[NoteSearchResult])
async def search_notes(query: str, collection: str, session: Session = Depends(get_session)) -> list[NoteSearchResult]:
    try:
        col = Collection(collection)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unknown collection: {collection!r}. Valid: {[c.value for c in Collection]}"
        )
    results = Note.search(session, query, collection=col)
    return [
        NoteSearchResult(id=n.id, title=n.title, body=n.body, collection=n.collection.value, tags=n.tags, dist=dist)
        for n, dist in results
    ]


class NoteCreateIn(BaseModel):
    title: str
    body: str
    collection: str
    tags: Optional[str] = None


@router.post("/notes", response_model=str)
async def create_note(body: NoteCreateIn, session: Session = Depends(get_session)) -> str:
    try:
        collection = Collection(body.collection)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown collection: {body.collection!r}")
    note = Note.create(session, title=body.title, body=body.body, collection=collection, tags=body.tags)
    session.commit()
    return repr(note)


class NoteUpdateIn(BaseModel):
    id: Optional[int] = None
    find: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[str] = None
    collection: Optional[str] = None


@router.patch("/notes", response_model=str)
async def update_note(body: NoteUpdateIn, session: Session = Depends(get_session)) -> str:
    note: Optional[Note]
    if body.id is not None:
        note = Note.get(session, body.id)
    elif body.find is not None:
        note = Note.find(session, body.find)
    else:
        raise HTTPException(status_code=400, detail="note update requires 'id' or 'find'")
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    collection: Optional[Collection] = None
    if body.collection is not None:
        try:
            collection = Collection(body.collection)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown collection: {body.collection!r}")
    note.update(title=body.title, body=body.body, tags=body.tags, collection=collection)
    session.commit()
    return repr(note)
