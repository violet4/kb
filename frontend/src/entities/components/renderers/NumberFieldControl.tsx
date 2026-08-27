import { useState } from 'react';
import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import type { ColumnSchema, EntityRow, EntityType } from '../../types';

interface NumberFieldControlProps {
  type: EntityType;
  id: number;
  schema: ColumnSchema;
  initialValue: string;
  onSaved: (entity: EntityRow) => void;
  onCancel: () => void;
}

// Click-to-edit + explicit Save/Cancel for number columns, the numeric counterpart
// to EditableFieldControl (text) -- same edit-session shape, a number input instead
// of a textarea.
export default function NumberFieldControl({ type, id, schema, initialValue, onSaved, onCancel }: NumberFieldControlProps) {
  const [value, setValue] = useState(initialValue);
  const { save, saving, error } = useFieldEdit(type, id, schema.name);

  const handleSave = () => {
    save(value).then(onSaved).catch(() => {});
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onCancel();
    if (e.key === 'Enter') handleSave();
  };

  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <input
        type="number"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
        style={inputStyle}
      />
      <button onClick={handleSave} disabled={saving} style={buttonStyle}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      <button onClick={onCancel} disabled={saving} style={buttonStyle}>
        Cancel
      </button>
      {error && <span style={{ fontSize: 12, color: tokens.color.danger }}>{error}</span>}
    </div>
  );
}

const inputStyle = {
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  padding: '4px 8px',
  fontSize: 13,
  fontFamily: 'inherit',
  width: 90,
} as const;

const buttonStyle = {
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  padding: '4px 8px',
  fontSize: 12,
  cursor: 'pointer',
} as const;
