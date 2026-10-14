"""Generic entity API: column introspection, list-with-filters, get-one, graph
neighbors (EntityLink), and Journal history -- backs the frontend's entity table/
drilldown views, the same way dailies_router.py backs the Dailies view but generic
across entity types instead of one hardcoded model. Deliberately scoped to the entity
types the UI actually renders rather than every mapped class -- add a type to
ENTITY_TYPES when a new type needs a table/drilldown view, not preemptively for
every model in the models package.

Columns are introspected live from each model's SQLAlchemy mapper (see
_introspect_columns), not hand-listed -- a new column on an existing type (or a new
enum value) needs no change here to show up in /columns, /fields, filtering, or the
generic list/detail responses. shown/editable/nullable are all derived structurally
(see _introspect_columns) rather than hand-picked per type."""

from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from api.deps import get_session
from models.base import UtcDateTime, _now
from context import PlacementError, place, placement_kind, placement_required
from archivebox_compat.config import ArchiveBoxConfigError
from kb_cli.archivebox import archivebox_url
from models.context import Context, ContextError, Tag
from models.journal.journal import Journal, JournalAction
from models.journal.tracking import HasJournal
from models.knowledge.archived_link import ArchivedLink
from models.knowledge.instruction import Instruction
from models.knowledge.log_entry import LogEntry
from models.knowledge.note import Note
from models.links.entity_link import EntityLink
from models.work.daily import Daily
from models.work.event import Event
from models.work.goal import Goal
from models.work.idea import Idea
from models.work.todo import Todo
from models.work.wishlist import Wishlist

router = APIRouter(prefix="/entities")

ENTITY_TYPES: dict[str, type[Any]] = {
    "Todo": Todo,
    "Goal": Goal,
    "Note": Note,
    "Idea": Idea,
    "Wishlist": Wishlist,
    "Instruction": Instruction,
    "Daily": Daily,
    "Event": Event,
    "ArchivedLink": ArchivedLink,
    "LogEntry": LogEntry,
}

# Columns hidden from every introspected view (internal bookkeeping, never a useful
# browse/filter/edit target) -- everything else on a model's mapper is generic.
_HIDDEN_COLUMNS = {"embedding", "embedding_model"}

# Relationships folded into the single placement column (named "context") for any placeable type.
_PLACEMENT_RELATIONSHIPS = {"context", "tag"}

# Column names carrying record-lifecycle metadata rather than user-editable content --
# structural (every model writes these via models/base.py's _now(), see CLAUDE.md), not a
# per-type editorial choice, so a new model needs no entry here to get this right.
_TIMESTAMP_COLUMNS = {"created_at", "updated_at"}

# Kinds a concrete frontend editor exists for today (BoolFieldToggle, EnumFieldSelect,
# EditableFieldControl, NumberFieldControl -- see Field.tsx/EntityTable.tsx). "utc_datetime" and
# "reference" render read-only until a matching editor is written; adding one here (and
# in the frontend) is what extends editability to that kind everywhere at once.
_EDITABLE_KINDS = {"bool", "enum", "text", "number"}


def _model_or_404(entity_type: str) -> type[Any]:
    model = ENTITY_TYPES.get(entity_type)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown entity type: {entity_type!r}")
    return model


def _get_or_404(session: Session, entity_type: str, entity_id: int) -> Any:
    model = _model_or_404(entity_type)
    row = session.get(model, entity_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{entity_type}:{entity_id} not found")
    return row


def _label(row: Any) -> str:
    return (
        getattr(row, "title", None)
        or getattr(row, "name", None)
        or getattr(row, "description", None)
        or getattr(row, "body", None)
        or repr(row)
    )


def _fk_to_relationship(model: type[Any]) -> dict[str, str]:
    """{foreign_key_column_name: relationship_name} for every relationship backed by a
    single local FK column (Todo.context_id -> "context", etc.) -- used to suppress the
    raw _id column from the generic column list in favor of the resolved relationship,
    the same way the old hand-written code exposed context_name instead of context_id."""
    result = {}
    for rel in inspect(model).relationships:
        if rel.local_remote_pairs and len(rel.local_remote_pairs) == 1:
            local_col = rel.local_remote_pairs[0][0]
            result[local_col.name] = rel.key
    return result


class ColumnSchema(BaseModel):
    name: str
    kind: str  # "text", "enum", "bool", "number", "utc_datetime", "reference", or "placement"
    choices: Optional[list[str]] = None  # populated only when kind == "enum"
    shown: bool  # whether this type's browse table shows this column by default
    editable: bool
    nullable: bool  # whether this editable column may be cleared back to NULL


def _column_kind(col: Any) -> tuple[str, Optional[list[str]]]:
    enum_cls = getattr(col.type, "enum_class", None)
    if enum_cls is not None:
        return "enum", [m.value for m in enum_cls]
    type_name = type(col.type).__name__
    if type_name == "Boolean":
        return "bool", None
    if type_name in ("Integer", "Numeric", "Float"):
        return "number", None
    if isinstance(col.type, UtcDateTime):
        return "utc_datetime", None
    return "text", None


def _introspect_columns(entity_type: str, model: type[Any]) -> list[ColumnSchema]:
    """Every real column on this model's mapper, minus internal bookkeeping and raw FK
    ids that a relationship already resolves -- the one place "what columns does this
    type have" is decided, shared by /columns, /fields, list filtering, and row
    serialization so all four always agree.

    shown/editable/nullable are all derived structurally rather than hand-picked per
    type: every non-hidden column is shown; a column is editable iff its kind has a
    frontend editor (_EDITABLE_KINDS) and it isn't a PK or a lifecycle timestamp
    (FK id columns never reach here at all -- see the fk_relationships skip below);
    nullable mirrors the actual DB nullability. A new column or a new model needs no
    entry anywhere in this file to show up correctly editable/read-only."""
    fk_relationships = _fk_to_relationship(model)
    schemas = []
    for col in inspect(model).columns:
        if col.name in _HIDDEN_COLUMNS or col.name in fk_relationships:
            continue
        kind, choices = _column_kind(col)
        read_only = col.primary_key or col.name in _TIMESTAMP_COLUMNS
        editable = kind in _EDITABLE_KINDS and not read_only
        schemas.append(
            ColumnSchema(
                name=col.name,
                kind=kind,
                choices=choices,
                shown=True,
                editable=editable,
                nullable=editable and col.nullable,
            )
        )
    # Where the row lives is one "context" column of kind "placement" (a context, or a tag where the type allows
    # it), first so it sits right after the title -- not two raw reference columns.
    placeable = placement_kind(model) is not None
    for rel_name in sorted(set(fk_relationships.values())):
        if placeable and rel_name in _PLACEMENT_RELATIONSHIPS:
            continue
        schemas.append(ColumnSchema(name=rel_name, kind="reference", shown=True, editable=False, nullable=False))
    if placeable:
        placement = ColumnSchema(
            name="context", kind="placement", shown=True, editable=True, nullable=not placement_required(model)
        )
        schemas.insert(0, placement)
    return schemas


@router.get("/types", response_model=list[str])
async def list_entity_types() -> list[str]:
    return list(ENTITY_TYPES.keys())


@router.get("/{entity_type}/columns", response_model=list[ColumnSchema])
async def list_columns(entity_type: str) -> list[ColumnSchema]:
    """Every real column this type has, with enough metadata (kind, enum choices,
    whether it's shown by default, whether it's editable) for the frontend to build
    its table, filters, and available-but-unused list without any per-type frontend
    code. Registered before /{entity_type}/{entity_id} so "columns" isn't swallowed
    as an entity_id."""
    model = _model_or_404(entity_type)
    return _introspect_columns(entity_type, model)


@router.get("/{entity_type}/fields", response_model=list[ColumnSchema])
async def list_editable_fields(entity_type: str) -> list[ColumnSchema]:
    """Back-compat alias for /columns, filtered to editable=True -- kept as its own
    path since EntityView's field-editing code already depends on this exact shape.
    Registered before /{entity_type}/{entity_id} for the same routing reason as /columns."""
    model = _model_or_404(entity_type)
    return [c for c in _introspect_columns(entity_type, model) if c.editable]


class Ref(BaseModel):
    id: int
    name: str


class PlacementOut(BaseModel):
    context: Optional[Ref]
    tag: Optional[Ref]
    tag_allowed: bool


def _placement(row: Any) -> PlacementOut:
    context, tag = getattr(row, "context", None), getattr(row, "tag", None)
    return PlacementOut(
        context=Ref(id=context.id, name=context.name) if context is not None else None,
        tag=Ref(id=tag.id, name=tag.name) if tag is not None else None,
        tag_allowed=placement_kind(type(row)) == "context_or_tag",
    )


def _row_value(row: Any, column: ColumnSchema) -> Any:
    if column.kind == "placement":
        return _placement(row).model_dump()
    if column.kind == "reference":
        other = getattr(row, column.name, None)
        return _label(other) if other is not None else None
    value = getattr(row, column.name, None)
    if value is None:
        return None
    if hasattr(value, "value"):  # Enum member -> its string value
        return value.value
    if hasattr(value, "isoformat"):  # datetime/date
        return value.isoformat()
    if type(value).__name__ == "Decimal":
        return float(value)
    return value


def _to_row(entity_type: str, row: Any, columns: list[ColumnSchema]) -> dict[str, Any]:
    return {
        "type": entity_type,
        "id": row.id,
        "label": _label(row),
        **{c.name: _row_value(row, c) for c in columns},
    }


def _apply_column_filter(q: Any, model: type[Any], entity_type: str, column: ColumnSchema, value: str) -> Any:
    db_column = getattr(model, column.name, None)
    if db_column is None:
        raise HTTPException(status_code=400, detail=f"{entity_type} has no filterable column {column.name!r}")
    if column.kind == "enum":
        # Comma-separated -- lets a multi-select filter (e.g. status=active,on_hold)
        # match any of several values via IN, not just one via equality.
        enum_cls = db_column.property.columns[0].type.enum_class
        try:
            members = [enum_cls(v) for v in value.split(",") if v]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown {column.name}: {value!r}")
        return q.where(db_column.in_(members))
    if column.kind == "bool":
        return q.where(db_column.is_(value.lower() in ("1", "true", "yes")))
    if column.kind == "number":
        return q.where(db_column == value)
    return q.where(db_column.ilike(f"%{value}%"))


@router.get("/{entity_type}")
async def list_entities(
    entity_type: str, request: Request, session: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    """Every column this type has is a valid filter -- `?status=pending`, `?kind=bug`,
    `?title=fix` (substring for text columns, exact match for enum/bool/number) --
    with no per-column endpoint parameter to add as new columns appear. Any query
    param not matching a real column name is ignored rather than erroring, so the
    frontend can always pass e.g. an empty string filter without special-casing it."""
    model = _model_or_404(entity_type)
    columns = _introspect_columns(entity_type, model)
    by_name = {c.name: c for c in columns}
    q = select(model)
    for param, value in request.query_params.items():
        if not value:
            continue
        column = by_name.get(param)
        if column is None or column.kind in ("reference", "placement"):
            continue
        q = _apply_column_filter(q, model, entity_type, column, value)
    rows = session.scalars(q.order_by(model.updated_at.desc())).all()
    return [_to_row(entity_type, r, columns) for r in rows]


@router.get("/{entity_type}/{entity_id}")
async def get_entity(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    model = _model_or_404(entity_type)
    row = _get_or_404(session, entity_type, entity_id)
    columns = _introspect_columns(entity_type, model)
    result = _to_row(entity_type, row, columns)
    if isinstance(row, ArchivedLink) and row.ab_id:
        try:
            index_url = archivebox_url(session, f"archive/{row.ab_id}/")
            result["index_url"] = index_url
            result["singlefile_url"] = index_url + "singlefile.html"
        except ArchiveBoxConfigError:
            pass
    return result


class FieldUpdateIn(BaseModel):
    field: str
    value: str = ""
    is_null: bool = False  # when true, clears the column to NULL and ignores `value`


@router.patch("/{entity_type}/{entity_id}")
async def update_entity_field(
    entity_type: str, entity_id: int, body: FieldUpdateIn, session: Session = Depends(get_session)
) -> dict[str, Any]:
    model = _model_or_404(entity_type)
    row = _get_or_404(session, entity_type, entity_id)
    columns = _introspect_columns(entity_type, model)
    by_name = {c.name: c for c in columns}
    column = by_name.get(body.field)
    if column is None or not column.editable or column.kind == "placement":
        raise HTTPException(status_code=400, detail=f"{entity_type}.{body.field} is not editable")
    if body.is_null and not column.nullable:
        raise HTTPException(status_code=400, detail=f"{entity_type}.{body.field} is not nullable")

    new_value: Any
    if body.is_null:
        new_value = None
    elif column.kind == "enum":
        enum_cls = getattr(model, body.field).property.columns[0].type.enum_class
        try:
            new_value = enum_cls(body.value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown {body.field}: {body.value!r}")
    elif column.kind == "number":
        try:
            new_value = int(body.value) if "." not in body.value else float(body.value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{body.field} must be a number, got {body.value!r}")
    elif column.kind == "bool":
        new_value = body.value.lower() in ("1", "true", "yes")
    else:
        new_value = body.value
    setattr(row, body.field, new_value)
    session.commit()
    session.refresh(row)
    return _to_row(entity_type, row, columns)


def _set_deleted(session: Session, entity_type: str, entity_id: int, deleted: bool) -> dict[str, Any]:
    """Soft delete or restore: deleted_at drops the row out of list/search/active views while
    keeping it reachable here, the same reversible delete as `kb <noun> delete`."""
    model = _model_or_404(entity_type)
    row = _get_or_404(session, entity_type, entity_id)
    try:
        row.deleted_at = _now() if deleted else None
    except ContextError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(row)
    return _to_row(entity_type, row, _introspect_columns(entity_type, model))


@router.delete("/{entity_type}/{entity_id}")
async def delete_entity(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    return _set_deleted(session, entity_type, entity_id, deleted=True)


@router.post("/{entity_type}/{entity_id}/restore")
async def restore_entity(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    return _set_deleted(session, entity_type, entity_id, deleted=False)


class PlacementIn(BaseModel):
    context_id: Optional[int] = None
    tag_id: Optional[int] = None  # at most one of the two; neither clears an optional placement


def _placement_label(p: PlacementOut) -> Optional[str]:
    return f"#{p.tag.name}" if p.tag else p.context.name if p.context else None


@router.put("/{entity_type}/{entity_id}/placement", response_model=PlacementOut)
def set_placement(
    entity_type: str, entity_id: int, body: PlacementIn, session: Session = Depends(get_session)
) -> PlacementOut:
    """Move any placeable row (not only ENTITY_TYPES -- search hits include Items, Vendors,
    ...) to a context or tag, via context.place, journaling the old and new location."""
    row = EntityLink.resolve(session, entity_type, entity_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{entity_type}:{entity_id} not found")
    context = session.get(Context, body.context_id) if body.context_id is not None else None
    tag = session.get(Tag, body.tag_id) if body.tag_id is not None else None
    if (body.context_id is not None and context is None) or (body.tag_id is not None and tag is None):
        raise HTTPException(status_code=400, detail="no such context/tag")
    old = _placement_label(_placement(row))
    try:
        place(row, context=context, tag=tag)
    except (PlacementError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e))
    result = _placement(row)
    if not isinstance(row, HasJournal):  # a HasJournal row journals its own change
        Journal.record(
            session,
            entity_type,
            entity_id,
            action=JournalAction.UPDATE,
            field="context",
            old_value=old,
            new_value=_placement_label(result),
        )
    session.commit()
    return result


class GraphNeighbor(BaseModel):
    link_id: int
    relation: str
    direction: str  # "outgoing" (this row is A) or "incoming" (this row is B)
    note: Optional[str]
    other_type: str
    other_id: int
    other_label: str
    other_exists: bool


@router.get("/{entity_type}/{entity_id}/graph", response_model=list[GraphNeighbor])
async def get_entity_graph(
    entity_type: str, entity_id: int, session: Session = Depends(get_session)
) -> list[GraphNeighbor]:
    _get_or_404(session, entity_type, entity_id)
    links = EntityLink.for_entity(session, entity_type, entity_id)
    neighbors = []
    for link in links:
        other_type, other_id = link.other_side(entity_type, entity_id)
        direction = "outgoing" if (link.type_a, link.id_a) == (entity_type, entity_id) else "incoming"
        other_row = EntityLink.resolve(session, other_type, other_id)
        neighbors.append(
            GraphNeighbor(
                link_id=link.id,
                relation=link.relation,
                direction=direction,
                note=link.note,
                other_type=other_type,
                other_id=other_id,
                other_label=_label(other_row) if other_row is not None else f"{other_type}:{other_id}",
                other_exists=other_row is not None,
            )
        )
    return neighbors


class EntityRefIn(BaseModel):
    type: str
    id: int


class EntityLabel(BaseModel):
    type: str
    id: int
    label: str


@router.post("/labels", response_model=list[EntityLabel])
async def resolve_entity_labels(refs: list[EntityRefIn], session: Session = Depends(get_session)) -> list[EntityLabel]:
    """Batch-resolve (type, id) pairs to display labels -- backs frontend title-embedding
    for inline TYPE:ID references (see linkifyEntityRefs.ts), so a body full of refs needs
    one round trip instead of one per ref. Refs that don't resolve (unknown type, deleted
    row) are omitted rather than erroring, since a body can freely mix live and stale refs."""
    labels = []
    seen: set[tuple[str, int]] = set()
    for ref in refs:
        key = (ref.type, ref.id)
        if key in seen:
            continue
        seen.add(key)
        row = EntityLink.resolve(session, ref.type, ref.id)
        if row is not None:
            labels.append(EntityLabel(type=ref.type, id=ref.id, label=_label(row)))
    return labels


def _new_wishlist(session: Session, title: str, context: Context) -> Wishlist:
    item = Wishlist(title=title, context=context)
    session.add(item)
    return item


# How a title alone becomes a new row, per type that supports quick creation. Every other
# field is set afterwards on the entity page, one field at a time.
_QUICK_CREATORS: dict[str, Callable[[Session, str, Context], Any]] = {
    "Goal": lambda session, title, context: Goal.create(session, title, context=context),
    "Todo": lambda session, title, context: Todo.create(session, title, context=context),
    "Note": lambda session, title, context: Note.create(session, title, "", context=context),
    "Wishlist": _new_wishlist,
}


class QuickCreateIn(BaseModel):
    title: str
    context_id: int


# Defined after /labels so that route's literal path wins over this one's {entity_type}.
@router.post("/{entity_type}")
async def quick_create(
    entity_type: str, body: QuickCreateIn, session: Session = Depends(get_session)
) -> dict[str, Any]:
    create = _QUICK_CREATORS.get(entity_type)
    if create is None:
        raise HTTPException(status_code=400, detail=f"{entity_type} has no quick create")
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is empty")
    context = session.get(Context, body.context_id)
    if context is None or context.deleted_at is not None:
        raise HTTPException(status_code=400, detail=f"Context:{body.context_id} not found")
    row = create(session, title, context)
    session.commit()
    return _to_row(entity_type, row, _introspect_columns(entity_type, ENTITY_TYPES[entity_type]))


class JournalEntry(BaseModel):
    id: int
    action: str
    session_id: Optional[str]  # the harness's own session id, for /agents/{session_id}
    field: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    note: Optional[str]
    created_at_utc: str


@router.get("/{entity_type}/{entity_id}/journal", response_model=list[JournalEntry])
async def get_entity_journal(
    entity_type: str, entity_id: int, session: Session = Depends(get_session)
) -> list[JournalEntry]:
    _get_or_404(session, entity_type, entity_id)
    entries = Journal.for_entity(session, entity_type, entity_id)
    return [
        JournalEntry(
            id=e.id,
            action=e.action.value,
            session_id=e.harness_session.harness_id if e.harness_session else None,
            field=e.field,
            old_value=e.old_value,
            new_value=e.new_value,
            note=e.note,
            created_at_utc=e.created_at.isoformat(),
        )
        for e in entries
    ]
