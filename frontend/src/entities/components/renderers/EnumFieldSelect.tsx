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
// A nullable enum's empty value gets its own blank option (rather than Field
// gating this control behind a separate null-placeholder state, see Field.tsx) --
// so a null row shows an actually-blank selection, not a silently-wrong first
// choice the browser falls back to when `value` matches no <option>.
export default function EnumFieldSelect({ type, id, schema, value, onSaved }: EnumFieldSelectProps) {
  const { save, clear, saving, error } = useFieldEdit(type, id, schema.name);

  const handleChange = (newValue: string) => {
    const request = newValue === '' ? clear() : save(newValue);
    request.then(onSaved).catch(() => {});
  };

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <select value={value} disabled={saving} onChange={(e) => handleChange(e.target.value)} style={selectStyle}>
        {schema.nullable && <option value="">null</option>}
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
