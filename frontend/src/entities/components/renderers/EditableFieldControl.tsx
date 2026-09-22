import { useState } from 'react';
import Markdown from '../../../shared/Markdown';
import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import type { ColumnSchema, EntityRow, EntityType } from '../../types';

interface EditableFieldControlProps {
  type: EntityType;
  id: number;
  schema: ColumnSchema;
  initialValue: string;
  onSaved: (entity: EntityRow) => void;
  onCancel: () => void;
  // Render a side-by-side live-preview pane next to the textarea while editing --
  // for the same long-form body fields (Body/Description/Notes) that already render
  // as markdown in the non-editing view (see Field's `markdown` prop), so editing
  // doesn't lose that context.
  markdown?: boolean;
}

// Click-to-edit + explicit Save/Cancel for text fields -- a keystroke isn't a
// complete value the way picking a dropdown option is, so unlike EnumFieldSelect
// this needs a real edit session rather than saving on every change.
export default function EditableFieldControl({ type, id, schema, initialValue, onSaved, onCancel, markdown }: EditableFieldControlProps) {
  const [value, setValue] = useState(initialValue);
  const { save, saving, error } = useFieldEdit(type, id, schema.name);

  const handleSave = () => {
    save(value).then(onSaved).catch(() => {});
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onCancel();
  };

  const textarea = (
    <textarea
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      autoFocus
      rows={textareaRows(value)}
      style={{ ...inputStyle, width: '100%', resize: 'vertical', whiteSpace: 'pre-wrap' }}
    />
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '100%' }}>
      {markdown ? (
        <div style={{ display: 'flex', gap: 16, width: '100%', alignItems: 'stretch' }}>
          <div style={{ flex: 1, minWidth: 0 }}>{textarea}</div>
          <div
            style={{
              flex: 1,
              minWidth: 0,
              border: `1px solid ${tokens.color.border}`,
              borderRadius: 4,
              padding: '4px 8px',
              overflowY: 'auto',
              maxHeight: textareaRows(value) * 20 + 16,
            }}
          >
            <Markdown text={value} />
          </div>
        </div>
      ) : (
        textarea
      )}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <button onClick={handleSave} disabled={saving} style={buttonStyle}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button onClick={onCancel} disabled={saving} style={buttonStyle}>
          Cancel
        </button>
        {error && <span style={{ fontSize: 12, color: tokens.color.danger }}>{error}</span>}
      </div>
    </div>
  );
}

// Sized to fit the existing content up front (explicit newlines plus an estimate for
// wrapped lines at this field's width) rather than a fixed short default -- a long
// Note body or Todo description otherwise opens into a tiny scrollable box.
function textareaRows(value: string): number {
  const CHARS_PER_LINE = 90;
  const explicitLines = value.split('\n').length;
  const wrappedLines = Math.ceil(value.length / CHARS_PER_LINE);
  return Math.min(24, Math.max(3, explicitLines, wrappedLines));
}

const inputStyle = {
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  padding: '4px 8px',
  fontSize: 13,
  fontFamily: 'inherit',
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
