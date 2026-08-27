import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import type { ColumnSchema, EntityRow, EntityType } from '../../types';

interface EnumFieldSelectProps {
  type: EntityType;
  id: number;
  schema: ColumnSchema;
  value: string;
  onSaved: (entity: EntityRow) => void;
}

// Always a live dropdown, no click-to-reveal and no Save/Cancel -- picking a new
// option saves immediately. Distinct from the text field's EditableFieldControl,
// which needs an explicit save step since a keystroke isn't a complete value.
export default function EnumFieldSelect({ type, id, schema, value, onSaved }: EnumFieldSelectProps) {
  const { save, saving, error } = useFieldEdit(type, id, schema.name);

  const handleChange = (newValue: string) => {
    save(newValue).then(onSaved).catch(() => {});
  };

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <select value={value} disabled={saving} onChange={(e) => handleChange(e.target.value)} style={selectStyle}>
        {(schema.choices ?? []).map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
      {error && <span style={{ fontSize: 12, color: tokens.color.danger }}>{error}</span>}
    </div>
  );
}

const selectStyle = {
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  padding: '4px 8px',
  fontSize: 13,
  fontFamily: 'inherit',
} as const;
