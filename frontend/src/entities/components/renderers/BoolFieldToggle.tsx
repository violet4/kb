import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import type { ColumnSchema, EntityRow, EntityType } from '../../types';

interface BoolFieldToggleProps {
  type: EntityType;
  id: number;
  schema: ColumnSchema;
  value: boolean;
  onSaved: (entity: EntityRow) => void;
}

// Always a live checkbox, no click-to-reveal and no Save/Cancel -- toggling saves
// immediately, the same "picking a value is a complete action" reasoning as
// EnumFieldSelect (a checked/unchecked state isn't a partial keystroke).
export default function BoolFieldToggle({ type, id, schema, value, onSaved }: BoolFieldToggleProps) {
  const { save, saving, error } = useFieldEdit(type, id, schema.name);

  const handleChange = (checked: boolean) => {
    save(String(checked)).then(onSaved).catch(() => {});
  };

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input type="checkbox" checked={value} disabled={saving} onChange={(e) => handleChange(e.target.checked)} />
      {error && <span style={{ fontSize: 12, color: tokens.color.danger }}>{error}</span>}
    </div>
  );
}
