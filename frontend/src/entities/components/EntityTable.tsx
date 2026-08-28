import { useState } from 'react';
import { Link } from 'react-router-dom';
import { tokens } from '../../shared/tokens';
import { entityPath } from '../navigation';
import { useFieldEdit } from '../hooks/useFieldEdit';
import type { ColumnSchema, EntityRow } from '../types';
import BoolFieldToggle from './renderers/BoolFieldToggle';
import EditableFieldControl from './renderers/EditableFieldControl';
import EnumFieldSelect from './renderers/EnumFieldSelect';
import NullableFieldWrapper from './renderers/NullableFieldWrapper';
import NumberFieldControl from './renderers/NumberFieldControl';

interface EntityTableProps {
  entities: EntityRow[];
  columns: ColumnSchema[];
  titleSchema?: ColumnSchema;
  onFieldSaved: (entity: EntityRow) => void;
}

// null/undefined sort last regardless of direction -- otherwise every column would
// need its own "where do missing values go" judgment call each time it's sorted.
function compareValues(a: unknown, b: unknown): number {
  const aEmpty = a === null || a === undefined;
  const bEmpty = b === null || b === undefined;
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b);
  return String(a).localeCompare(String(b));
}

type SortDirection = 'asc' | 'desc';
interface SortState {
  column: string; // column name, or '__label' for the fixed leading Title column
  direction: SortDirection;
}

// Fully column-driven: which columns to render, their labels, and whether a cell is
// a live editable dropdown all come from `columns` (introspected once by BrowseView)
// -- adding a column to a type's DEFAULT_COLUMNS on the backend is the only change
// needed for it to appear here, no frontend edit. Sorting is likewise generic: any
// column (plus the fixed Title column) is sortable by clicking its header, cycling
// asc -> desc -> unsorted, sorting whatever value formatCellValue would display for
// that column rather than needing its own per-kind comparator wired in by hand.
export default function EntityTable({ entities, columns, titleSchema, onFieldSaved }: EntityTableProps) {
  const [sort, setSort] = useState<SortState | null>(null);

  const handleHeaderClick = (column: string) => {
    setSort((prev) => {
      if (prev?.column !== column) return { column, direction: 'asc' };
      if (prev.direction === 'asc') return { column, direction: 'desc' };
      return null;
    });
  };

  const sortedEntities = sort
    ? [...entities].sort((a, b) => {
        const key = sort.column === '__label' ? 'label' : sort.column;
        const cmp = compareValues(a[key], b[key]);
        return sort.direction === 'asc' ? cmp : -cmp;
      })
    : entities;

  if (entities.length === 0) return <p style={{ color: tokens.color.textMuted }}>Nothing here.</p>;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: 'left', color: tokens.color.textMuted }}>
            <SortableHeader label="Title" column="__label" sort={sort} onClick={handleHeaderClick} />
            {columns.map((column) => (
              <SortableHeader
                key={column.name}
                label={columnLabel(column.name)}
                column={column.name}
                sort={sort}
                onClick={handleHeaderClick}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedEntities.map((entity) => (
            <EntityTableRow
              key={`${entity.type}:${entity.id}`}
              entity={entity}
              columns={columns}
              titleSchema={titleSchema}
              onFieldSaved={onFieldSaved}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface SortableHeaderProps {
  label: string;
  column: string;
  sort: SortState | null;
  onClick: (column: string) => void;
}

function SortableHeader({ label, column, sort, onClick }: SortableHeaderProps) {
  const active = sort?.column === column;
  const indicator = active ? (sort.direction === 'asc' ? ' ▲' : ' ▼') : '';
  return (
    <th style={{ ...cellStyle, cursor: 'pointer', userSelect: 'none' }} onClick={() => onClick(column)}>
      {label}
      {indicator}
    </th>
  );
}

interface EntityTableRowProps {
  entity: EntityRow;
  columns: ColumnSchema[];
  titleSchema?: ColumnSchema;
  onFieldSaved: (entity: EntityRow) => void;
}

function EntityTableRow({ entity, columns, titleSchema, onFieldSaved }: EntityTableRowProps) {
  return (
    <tr style={{ borderTop: `1px solid ${tokens.color.border}` }}>
      <td style={cellStyle}>
        <TitleCell entity={entity} titleSchema={titleSchema} onFieldSaved={onFieldSaved} />
      </td>
      {columns.map((column) => (
        <td key={column.name} style={cellStyle}>
          <EntityTableCell entity={entity} column={column} onFieldSaved={onFieldSaved} />
        </td>
      ))}
    </tr>
  );
}

interface TitleCellProps {
  entity: EntityRow;
  titleSchema?: ColumnSchema;
  onFieldSaved: (entity: EntityRow) => void;
}

// The one cell that's both a navigation link and (when titleSchema is editable) an
// editable field -- competing interactions, so editing is a separate explicit
// affordance (a small pencil button) rather than overloading a click on the link
// itself, which always navigates.
function TitleCell({ entity, titleSchema, onFieldSaved }: TitleCellProps) {
  const [isEditing, setIsEditing] = useState(false);

  if (titleSchema?.editable && isEditing) {
    return (
      <EditableFieldControl
        type={entity.type}
        id={entity.id}
        schema={titleSchema}
        initialValue={entity.label}
        onSaved={(row) => {
          setIsEditing(false);
          onFieldSaved(row);
        }}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <Link to={entityPath(entity.type, entity.id)} style={tokens.link}>
        {entity.label}
      </Link>
      {titleSchema?.editable && (
        <button
          onClick={() => setIsEditing(true)}
          title="Edit title"
          style={{
            background: 'transparent',
            border: 'none',
            color: tokens.color.textMuted,
            cursor: 'pointer',
            fontSize: 12,
            padding: 0,
          }}
        >
          ✎
        </button>
      )}
    </div>
  );
}

interface EntityTableCellProps {
  entity: EntityRow;
  column: ColumnSchema;
  onFieldSaved: (entity: EntityRow) => void;
}

function EntityTableCell({ entity, column, onFieldSaved }: EntityTableCellProps) {
  const value = entity[column.name];
  const [isEditing, setIsEditing] = useState(false);
  const { clear, saving: clearing } = useFieldEdit(entity.type, entity.id, column.name);
  const isEmpty = value === null || value === undefined || value === '';

  if (column.editable && column.kind === 'enum' && !isEmpty) {
    return <EnumFieldSelect type={entity.type} id={entity.id} schema={column} value={String(value)} onSaved={onFieldSaved} />;
  }

  if (column.editable && column.kind === 'bool') {
    return <BoolFieldToggle type={entity.type} id={entity.id} schema={column} value={Boolean(value)} onSaved={onFieldSaved} />;
  }

  // A comma-joined list (e.g. Note.tags) has no natural wrap point as one string --
  // render each item as its own wrappable chip instead of stretching the column.
  if (column.name === 'tags' && typeof value === 'string' && value.includes(',')) {
    return <TagChips value={value} />;
  }

  if (column.editable && (column.kind === 'text' || column.kind === 'number')) {
    const control = isEditing ? (
      <InlineEditControl
        entity={entity}
        column={column}
        value={value}
        onSaved={(row) => {
          setIsEditing(false);
          onFieldSaved(row);
        }}
        onCancel={() => setIsEditing(false)}
      />
    ) : (
      <span style={{ cursor: 'pointer' }} onClick={() => setIsEditing(true)} title="Click to edit">
        {formatCellValue(value, column.kind)}
      </span>
    );
    if (!column.nullable) return control;
    return (
      <NullableFieldWrapper
        isNull={isEmpty && !isEditing}
        clearing={clearing}
        onClear={() => clear().then(onFieldSaved)}
        onSetValue={() => setIsEditing(true)}
      >
        {control}
      </NullableFieldWrapper>
    );
  }

  return <>{formatCellValue(value, column.kind)}</>;
}

interface InlineEditControlProps {
  entity: EntityRow;
  column: ColumnSchema;
  value: unknown;
  onSaved: (entity: EntityRow) => void;
  onCancel: () => void;
}

function InlineEditControl({ entity, column, value, onSaved, onCancel }: InlineEditControlProps) {
  const initialValue = value === null || value === undefined ? '' : String(value);
  if (column.kind === 'number') {
    return (
      <NumberFieldControl
        type={entity.type}
        id={entity.id}
        schema={column}
        initialValue={initialValue}
        onSaved={onSaved}
        onCancel={onCancel}
      />
    );
  }
  return (
    <EditableFieldControl
      type={entity.type}
      id={entity.id}
      schema={column}
      initialValue={initialValue}
      onSaved={onSaved}
      onCancel={onCancel}
    />
  );
}

function TagChips({ value }: { value: string }) {
  const tags = value
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 200 }}>
      {tags.map((tag) => (
        <span
          key={tag}
          style={{
            background: tokens.color.surface,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 3,
            padding: '1px 6px',
            fontSize: 12,
            whiteSpace: 'nowrap',
          }}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

function formatCellValue(value: unknown, kind: ColumnSchema['kind']): string {
  if (value === null || value === undefined) return 'null';
  if (value === '') return '';
  if (kind === 'date' && typeof value === 'string') return new Date(value).toLocaleDateString();
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  return String(value);
}

// "context" -> "Context", "price_min" -> "Price min" -- readable from a raw column
// name with no per-column label to maintain.
function columnLabel(name: string): string {
  const [first, ...rest] = name.split('_');
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ');
}

const cellStyle = { padding: '6px 8px' };
