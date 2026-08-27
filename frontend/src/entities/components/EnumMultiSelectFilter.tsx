import { tokens } from '../../shared/tokens';
import type { ColumnSchema } from '../types';

interface EnumMultiSelectFilterProps {
  column: ColumnSchema;
  value: string;
  onChange: (column: string, value: string) => void;
}

// Checkboxes over an enum column's choices, backed by one comma-joined filter value
// -- matches the backend's IN-based multi-value enum filter (api/entities_router.py's
// _apply_column_filter), so "show active + on_hold" is one filter value, not several
// separate ones. Generic over any enum column, not status-specific: any type whose
// enum column benefits from multi-select gets it automatically.
export default function EnumMultiSelectFilter({ column, value, onChange }: EnumMultiSelectFilterProps) {
  const selected = new Set(value ? value.split(',') : []);

  const toggle = (choice: string) => {
    const next = new Set(selected);
    if (next.has(choice)) next.delete(choice);
    else next.add(choice);
    onChange(column.name, [...next].join(','));
  };

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {(column.choices ?? []).map((choice) => (
        <label key={choice} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, color: tokens.color.text }}>
          <input type="checkbox" checked={selected.has(choice)} onChange={() => toggle(choice)} />
          {choice}
        </label>
      ))}
    </div>
  );
}
