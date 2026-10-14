"""Context-centred API: the context tree with per-node item counts, one context's
page (breadcrumb, children, and every Goal/Todo/Note filed under it), and creating or
re-parenting a context -- backs the frontend's Contexts view, the "everything about
hecate in one place" surface. Name uniqueness and cycle checks live on Context itself.

Which Goals/Todos count as open is decided by each model's own `.active()` (status
filter plus HasContextOrTag's tag fan-out), never re-derived here."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.context_homes import contexts_by_tag, home_context_ids
from api.deps import get_session
from api.serialize import utc_iso
from context import INBOX_CONTEXT_NAME, get_inbox_context
from models.context import Context, Tag
from models.knowledge.note import Note
from models.work.goal import Goal
from models.work.todo import Todo
from models.work.wishlist import Wishlist

router = APIRouter(prefix="/contexts")


class ContextRef(BaseModel):
    id: int
    name: str


class Counts(BaseModel):
    todos: int = 0
    goals: int = 0
    notes: int = 0
    wishlist: int = 0


class ContextNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    tags: list[str]
    counts: Counts  # items filed directly here (tag-addressed ones included), not in descendants
    pinned: bool = False  # shown at the top of the tree, never filtered out (the inbox)


def _live_contexts(session: Session) -> Sequence[Context]:
    return session.scalars(select(Context).where(Context.deleted_at.is_(None)).order_by(Context.name)).all()


@router.get("/tree", response_model=list[ContextNode])
def context_tree(session: Session = Depends(get_session)) -> list[ContextNode]:
    contexts = _live_contexts(session)
    by_tag = contexts_by_tag(session)

    counts: dict[int, Counts] = defaultdict(Counts)
    for todo in Todo.active(session, include_deferred=True):
        for cid in home_context_ids(todo, by_tag):
            counts[cid].todos += 1
    for goal in Goal.active(session):
        for cid in home_context_ids(goal, by_tag):
            counts[cid].goals += 1
    for note in session.scalars(select(Note).where(Note.deleted_at.is_(None))):
        counts[note.context_id].notes += 1
    for item in Wishlist.active(session):
        counts[item.context_id].wishlist += 1

    return [
        ContextNode(
            id=c.id,
            name=c.name,
            parent_id=c.parent_id,
            tags=[t.name for t in c.tags],
            counts=counts[c.id],
            pinned=c.name == INBOX_CONTEXT_NAME,
        )
        for c in contexts
    ]


@router.get("/tags", response_model=list[ContextRef])
def tags(session: Session = Depends(get_session)) -> list[ContextRef]:
    """Every live Tag -- the other half of a placement picker, for rows that can float on one."""
    rows = session.scalars(select(Tag).where(Tag.deleted_at.is_(None)).order_by(Tag.name))
    return [ContextRef(id=t.id, name=t.name) for t in rows]


@router.get("/inbox", response_model=ContextRef)
def inbox(session: Session = Depends(get_session)) -> ContextRef:
    context = get_inbox_context(session)
    session.commit()  # get_inbox_context creates it on first use
    return ContextRef(id=context.id, name=context.name)


class ContextCreate(BaseModel):
    name: str = Field(min_length=1)
    parent_id: Optional[int] = None


class ContextMove(BaseModel):
    parent_id: Optional[int]  # None makes the context top-level


def _live_context(session: Session, context_id: int, status_code: int = 404) -> Context:
    context = session.get(Context, context_id)
    if context is None or context.deleted_at is not None:
        raise HTTPException(status_code=status_code, detail=f"Context:{context_id} not found")
    return context


def _node(context: Context) -> ContextNode:
    return ContextNode(
        id=context.id,
        name=context.name,
        parent_id=context.parent_id,
        tags=[t.name for t in context.tags],
        counts=Counts(),
        pinned=context.name == INBOX_CONTEXT_NAME,
    )


@router.post("", response_model=ContextNode)
def create_context(payload: ContextCreate, session: Session = Depends(get_session)) -> ContextNode:
    parent = _live_context(session, payload.parent_id, 400) if payload.parent_id is not None else None
    try:
        context = Context.create(session, payload.name, parent=parent)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _node(context)


@router.put("/{context_id}/parent", response_model=ContextNode)
def move_context(context_id: int, payload: ContextMove, session: Session = Depends(get_session)) -> ContextNode:
    context = _live_context(session, context_id)
    parent = _live_context(session, payload.parent_id, 400) if payload.parent_id is not None else None
    try:
        context.move_under(parent)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _node(context)


class GoalItem(BaseModel):
    id: int
    title: str
    status: str
    context: Optional[ContextRef]
    via_tag: Optional[str]


class GoalRef(BaseModel):
    id: int
    title: str


class TodoItem(BaseModel):
    id: int
    title: str
    status: str
    kind: str
    effort: Optional[str]
    severity: Optional[str]
    resolution_distance: Optional[str]
    urgent: bool
    defer_until_utc: Optional[str]
    goal: Optional[GoalRef]
    context: Optional[ContextRef]
    via_tag: Optional[str]
    updated_at_utc: Optional[str]


class NoteItem(BaseModel):
    id: int
    title: str
    collection: str
    tags: Optional[str]
    context: ContextRef
    updated_at_utc: Optional[str]


class WishlistItem(BaseModel):
    id: int
    title: str
    price_min: Optional[float]
    price_max: Optional[float]
    priority: Optional[int]
    pinned: bool
    context: ContextRef


class ContextPage(BaseModel):
    context: ContextRef
    description: Optional[str]
    tags: list[str]
    ancestors: list[ContextRef]  # root first, excluding this context
    children: list[ContextRef]
    include_descendants: bool
    goals: list[GoalItem]
    todos: list[TodoItem]
    notes: list[NoteItem]
    wishlist: list[WishlistItem]


def _ref(context: Optional[Context]) -> Optional[ContextRef]:
    return ContextRef(id=context.id, name=context.name) if context is not None else None


@router.get("/{context_id}", response_model=ContextPage)
def context_page(
    context_id: int, include_descendants: bool = True, session: Session = Depends(get_session)
) -> ContextPage:
    context = _live_context(session, context_id)
    scope = Context.self_and_descendants(session, context.name) if include_descendants else [context]
    scope_ids = [c.id for c in scope]

    goals = sorted(Goal.active(session, contexts=scope), key=lambda g: g.id)
    todos = sorted(Todo.active(session, contexts=scope, include_deferred=True), key=Todo.triage_key)
    notes = session.scalars(
        select(Note).where(Note.deleted_at.is_(None), Note.context_id.in_(scope_ids)).order_by(Note.updated_at.desc())
    ).all()
    wishlist = Wishlist.top(session, n=1000, contexts=scope)
    children = session.scalars(
        select(Context).where(Context.parent_id == context.id, Context.deleted_at.is_(None)).order_by(Context.name)
    ).all()

    return ContextPage(
        context=ContextRef(id=context.id, name=context.name),
        description=context.description,
        tags=[t.name for t in context.tags],
        ancestors=[ContextRef(id=a.id, name=a.name) for a in reversed(context.ancestors()[1:])],
        children=[ContextRef(id=c.id, name=c.name) for c in children],
        include_descendants=include_descendants,
        goals=[
            GoalItem(
                id=g.id,
                title=g.title,
                status=g.status.value,
                context=_ref(g.context),
                via_tag=g.tag.name if g.tag else None,
            )
            for g in goals
        ],
        todos=[
            TodoItem(
                id=t.id,
                title=t.title,
                status=t.status.value,
                kind=t.kind.value,
                effort=t.effort.value if t.effort else None,
                severity=t.severity.value if t.severity else None,
                resolution_distance=t.resolution_distance.value if t.resolution_distance else None,
                urgent=t.urgent,
                defer_until_utc=utc_iso(t.defer_until),
                goal=GoalRef(id=t.goal.id, title=t.goal.title) if t.goal else None,
                context=_ref(t.context),
                via_tag=t.tag.name if t.tag else None,
                updated_at_utc=utc_iso(t.updated_at),
            )
            for t in todos
        ],
        notes=[
            NoteItem(
                id=n.id,
                title=n.title,
                collection=n.collection.value,
                tags=n.tags,
                context=ContextRef(id=n.context.id, name=n.context.name),
                updated_at_utc=utc_iso(n.updated_at),
            )
            for n in notes
        ],
        wishlist=[
            WishlistItem(
                id=w.id,
                title=w.title,
                price_min=float(w.price_min) if w.price_min is not None else None,
                price_max=float(w.price_max) if w.price_max is not None else None,
                priority=w.priority,
                pinned=w.pinned,
                context=ContextRef(id=w.context.id, name=w.context.name),
            )
            for w in wishlist
        ],
    )
