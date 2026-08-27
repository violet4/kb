import { tokens } from '../../shared/tokens';
import type { ColumnSchema } from '../types';

interface GenericFiltersProps {
  columns: ColumnSchema[];
  values: Record<string, string>;
  onChange: (column: string, value: string) => void;
}

// One filter control per shown, filterable column -- an enum column gets a dropdown
// (its choices come straight from the schema, same as EnumFieldSelect), everything
// else a text input. No per-type filter code: a new column added to a type's
// DEFAULT_COLUMNS just gets a filter automatically.
export default function GenericFilters({ columns, values, onChange }: GenericFiltersProps) {
  const filterable = columns.filter((c) => c.kind !== 'reference');
  if (filterable.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      {filterable.map((column) => (
        <ColumnFilter key={column.name} column={column} value={values[column.name] ?? ''} onChange={onChange} />
      ))}
    </div>
  );
}

interface ColumnFilterProps {
  column: ColumnSchema;
  value: string;
  onChange: (column: string, value: string) => void;
}

function ColumnFilter({ column, value, onChange }: ColumnFilterProps) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: tokens.color.textMuted }}>
      {column.name}
      <FilterControl column={column} value={value} onChange={onChange} />
    </label>
  );
}

function FilterControl({ column, value, onChange }: ColumnFilterProps) {
  if (column.kind === 'enum') {
    return (
      <select value={value} onChange={(e) => onChange(column.name, e.target.value)} style={controlStyle}>
        <option value="">(any)</option>
        {(column.choices ?? []).map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(column.name, e.target.value)}
      placeholder="(any)"
      style={controlStyle}
    />
  );
}

const controlStyle = {
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  padding: '4px 8px',
  fontSize: 13,
} as const;
