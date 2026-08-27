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
  onFieldSaved: (entity: EntityRow) => void;
}

// Fully column-driven: which columns to render, their labels, and whether a cell is
// a live editable dropdown all come from `columns` (introspected once by BrowseView)
// -- adding a column to a type's DEFAULT_COLUMNS on the backend is the only change
// needed for it to appear here, no frontend edit.
export default function EntityTable({ entities, columns, onFieldSaved }: EntityTableProps) {
  if (entities.length === 0) return <p style={{ color: tokens.color.textMuted }}>Nothing here.</p>;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: 'left', color: tokens.color.textMuted }}>
            <th style={cellStyle}>Title</th>
            {columns.map((column) => (
              <th key={column.name} style={cellStyle}>
                {columnLabel(column.name)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entities.map((entity) => (
            <EntityTableRow key={`${entity.type}:${entity.id}`} entity={entity} columns={columns} onFieldSaved={onFieldSaved} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface EntityTableRowProps {
  entity: EntityRow;
  columns: ColumnSchema[];
  onFieldSaved: (entity: EntityRow) => void;
}

function EntityTableRow({ entity, columns, onFieldSaved }: EntityTableRowProps) {
  return (
    <tr style={{ borderTop: `1px solid ${tokens.color.border}` }}>
      <td style={cellStyle}>
        <Link to={entityPath(entity.type, entity.id)} style={{ color: tokens.color.text, textDecoration: 'none' }}>
          {entity.label}
        </Link>
      </td>
      {columns.map((column) => (
        <td key={column.name} style={cellStyle}>
          <EntityTableCell entity={entity} column={column} onFieldSaved={onFieldSaved} />
        </td>
      ))}
    </tr>
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
  if (value === null || value === undefined || value === '') return '—';
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
