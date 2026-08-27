"""Generic entity API: column introspection, list-with-filters, get-one, graph
neighbors (EntityLink), and Journal history -- backs the frontend's entity table/
drilldown views, the same way dailies_router.py backs the Dailies view but generic
across entity types instead of one hardcoded model. Deliberately scoped to the entity
types the UI actually renders (Todo, Goal, Note, Idea, Wishlist) rather than every
mapped class -- add a type to ENTITY_TYPES when a new type needs a table/drilldown
view, not preemptively for every model in models.py.

Columns are introspected live from each model's SQLAlchemy mapper (see
_introspect_columns), not hand-listed -- a new column on an existing type (or a new
enum value) needs no change here to show up in /columns, /fields, filtering, or the
generic list/detail responses. DEFAULT_COLUMNS is the one hand-curated piece left:
which of those introspected columns a browse table shows by default versus lists as
merely available -- a deliberate editorial choice, not something to derive."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from api.deps import get_session
from models import EntityLink, Goal, Idea, Journal, Note, Todo, Wishlist

router = APIRouter(prefix="/entities")

ENTITY_TYPES: dict[str, type[Any]] = {
    "Todo": Todo,
    "Goal": Goal,
    "Note": Note,
    "Idea": Idea,
    "Wishlist": Wishlist,
}

# Columns hidden from every introspected view (internal bookkeeping, never a useful
# browse/filter/edit target) -- everything else on a model's mapper is generic.
_HIDDEN_COLUMNS = {"embedding", "embedding_model"}

# Which introspected columns a browse table shows by default, per type -- an editorial
# choice (what's actually useful at a glance), not derivable from the schema alone.
# Every other real column still appears via /columns for filtering, and is listed as
# "available but not shown" by the frontend so a missing-but-wanted one is easy to spot.
DEFAULT_COLUMNS: dict[str, tuple[str, ...]] = {
    "Todo": ("title", "status", "kind", "severity", "context", "updated_at"),
    "Goal": ("title", "status", "context", "updated_at"),
    "Note": ("title", "collection", "tags", "updated_at"),
    "Idea": ("title", "status", "context", "updated_at"),
    "Wishlist": ("title", "status", "priority", "context", "updated_at"),
}

# Columns editable via PATCH, per type -- a further-restricted subset of what's
# introspected (id/created_at/updated_at/long body-text fields are readable and
# filterable but not edited inline this way).
EDITABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "Todo": ("title", "status", "kind", "severity", "notes"),
    "Goal": ("title", "status", "description", "notes"),
    "Note": ("title", "collection", "tags", "body"),
    "Idea": ("title", "status", "description", "notes"),
    "Wishlist": ("title", "status", "priority", "notes"),
}

# Columns whose value may be cleared back to NULL via PATCH (see FieldUpdateIn.is_null)
# -- a further-restricted subset of EDITABLE_COLUMNS, since not every editable column
# is nullable at the DB level (e.g. Todo.title, Wishlist.status are NOT NULL).
NULLABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "Todo": ("severity", "notes"),
    "Goal": ("description", "notes"),
    "Note": ("tags",),
    "Idea": ("description", "notes"),
    "Wishlist": ("priority", "notes"),
}


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
    return getattr(row, "title", None) or getattr(row, "name", None) or getattr(row, "description", None) or repr(row)


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
    kind: str  # "text", "enum", "bool", "number", "date", or "reference"
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
    if type_name == "DateTime":
        return "date", None
    return "text", None


def _introspect_columns(entity_type: str, model: type[Any]) -> list[ColumnSchema]:
    """Every real column on this model's mapper, minus internal bookkeeping and raw FK
    ids that a relationship already resolves -- the one place "what columns does this
    type have" is decided, shared by /columns, /fields, list filtering, and row
    serialization so all four always agree."""
    fk_relationships = _fk_to_relationship(model)
    shown = set(DEFAULT_COLUMNS.get(entity_type, ()))
    editable = set(EDITABLE_COLUMNS.get(entity_type, ()))
    nullable = set(NULLABLE_COLUMNS.get(entity_type, ()))
    schemas = []
    for col in inspect(model).columns:
        if col.name in _HIDDEN_COLUMNS or col.name in fk_relationships:
            continue
        kind, choices = _column_kind(col)
        schemas.append(
            ColumnSchema(
                name=col.name,
                kind=kind,
                choices=choices,
                shown=col.name in shown,
                editable=col.name in editable,
                nullable=col.name in nullable,
            )
        )
    for rel_name in set(fk_relationships.values()):
        schemas.append(
            ColumnSchema(name=rel_name, kind="reference", shown=rel_name in shown, editable=False, nullable=False)
        )
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


def _row_value(row: Any, column: ColumnSchema) -> Any:
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
        enum_cls = db_column.property.columns[0].type.enum_class
        try:
            return q.where(db_column == enum_cls(value))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown {column.name}: {value!r}")
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
        if column is None or column.kind == "reference":
            continue
        q = _apply_column_filter(q, model, entity_type, column, value)
    rows = session.scalars(q.order_by(model.updated_at.desc())).all()
    return [_to_row(entity_type, r, columns) for r in rows]


@router.get("/{entity_type}/{entity_id}")
async def get_entity(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    model = _model_or_404(entity_type)
    row = _get_or_404(session, entity_type, entity_id)
    columns = _introspect_columns(entity_type, model)
    return _to_row(entity_type, row, columns)


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
    if column is None or not column.editable:
        raise HTTPException(status_code=400, detail=f"{entity_type}.{body.field} is not editable")
    if body.is_null and not column.nullable:
        raise HTTPException(status_code=400, detail=f"{entity_type}.{body.field} is not nullable")

    old_value = _row_value(row, column)
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
    else:
        new_value = body.value
    setattr(row, body.field, new_value)
    Journal.record(
        session,
        entity_type,
        entity_id,
        field=body.field,
        old_value=str(old_value) if old_value is not None else None,
        new_value=None if body.is_null else body.value,
    )
    session.commit()
    session.refresh(row)
    return _to_row(entity_type, row, columns)


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


class JournalEntry(BaseModel):
    id: int
    field: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    note: Optional[str]
    created_at: str


@router.get("/{entity_type}/{entity_id}/journal", response_model=list[JournalEntry])
async def get_entity_journal(
    entity_type: str, entity_id: int, session: Session = Depends(get_session)
) -> list[JournalEntry]:
    _get_or_404(session, entity_type, entity_id)
    entries = Journal.for_entity(session, entity_type, entity_id)
    return [
        JournalEntry(
            id=e.id,
            field=e.field,
            old_value=e.old_value,
            new_value=e.new_value,
            note=e.note,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
