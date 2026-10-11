"""Context-centred API: the context tree with per-node item counts, and one context's
page (breadcrumb, children, and every Goal/Todo/Note filed under it) -- backs the
frontend's Contexts view, the "everything about hecate in one place" surface.

Which Goals/Todos count as open is decided by each model's own `.active()` (status
filter plus HasContextOrTag's tag fan-out), never re-derived here."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from models import Context, Goal, Note, Todo

router = APIRouter(prefix="/contexts")


def _utc_iso(value: Optional[datetime]) -> Optional[str]:
    """SQLite hands back naive datetimes; every kb timestamp is written as UTC (base.py's
    _now()), so stamp the zone before serializing."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class ContextRef(BaseModel):
    id: int
    name: str


class Counts(BaseModel):
    todos: int = 0
    goals: int = 0
    notes: int = 0


class ContextNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    tags: list[str]
    counts: Counts  # items filed directly here (tag-addressed ones included), not in descendants


def _live_contexts(session: Session) -> Sequence[Context]:
    return session.scalars(select(Context).where(Context.deleted_at.is_(None)).order_by(Context.name)).all()


def _homes(row: Any, contexts_by_tag: dict[int, list[int]]) -> list[int]:
    """Context ids a Goal/Todo shows up under: its own context, or every context carrying its tag."""
    if row.context_id is not None:
        return [row.context_id]
    if getattr(row, "tag_id", None) is not None:
        return contexts_by_tag.get(row.tag_id, [])
    return []


@router.get("/tree", response_model=list[ContextNode])
def context_tree(session: Session = Depends(get_session)) -> list[ContextNode]:
    contexts = _live_contexts(session)
    contexts_by_tag: dict[int, list[int]] = defaultdict(list)
    for c in contexts:
        for tag in c.tags:
            contexts_by_tag[tag.id].append(c.id)

    counts: dict[int, Counts] = defaultdict(Counts)
    for todo in Todo.active(session, include_deferred=True):
        for cid in _homes(todo, contexts_by_tag):
            counts[cid].todos += 1
    for goal in Goal.active(session):
        for cid in _homes(goal, contexts_by_tag):
            counts[cid].goals += 1
    for note in session.scalars(select(Note).where(Note.deleted_at.is_(None), Note.context_id.is_not(None))):
        counts[note.context_id].notes += 1  # type: ignore[index]

    return [
        ContextNode(id=c.id, name=c.name, parent_id=c.parent_id, tags=[t.name for t in c.tags], counts=counts[c.id])
        for c in contexts
    ]


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
    context: Optional[ContextRef]
    updated_at_utc: Optional[str]


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


def _ref(context: Optional[Context]) -> Optional[ContextRef]:
    return ContextRef(id=context.id, name=context.name) if context is not None else None


@router.get("/{context_id}", response_model=ContextPage)
def context_page(
    context_id: int, include_descendants: bool = True, session: Session = Depends(get_session)
) -> ContextPage:
    context = session.get(Context, context_id)
    if context is None or context.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Context:{context_id} not found")
    scope = Context.self_and_descendants(session, context.name) if include_descendants else [context]
    scope_ids = [c.id for c in scope]

    goals = sorted(Goal.active(session, contexts=scope), key=lambda g: g.id)
    todos = sorted(Todo.active(session, contexts=scope, include_deferred=True), key=lambda t: t.id)
    notes = session.scalars(
        select(Note).where(Note.deleted_at.is_(None), Note.context_id.in_(scope_ids)).order_by(Note.updated_at.desc())
    ).all()
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
                urgent=t.urgent,
                defer_until_utc=_utc_iso(t.defer_until),
                goal=GoalRef(id=t.goal.id, title=t.goal.title) if t.goal else None,
                context=_ref(t.context),
                via_tag=t.tag.name if t.tag else None,
                updated_at_utc=_utc_iso(t.updated_at),
            )
            for t in todos
        ],
        notes=[
            NoteItem(
                id=n.id,
                title=n.title,
                collection=n.collection.value,
                tags=n.tags,
                context=_ref(n.context),
                updated_at_utc=_utc_iso(n.updated_at),
            )
            for n in notes
        ],
    )
