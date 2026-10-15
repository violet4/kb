import { useState } from 'react';
import Markdown from '../../../shared/Markdown';
import { isSubmitShortcut } from '../../../shared/submitShortcut';
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
    if (isSubmitShortcut(e)) {
      e.preventDefault();
      handleSave();
    }
  };

  const textarea = (sizing: React.CSSProperties) => (
    <textarea
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      autoFocus
      rows={textareaRows(value)}
      style={{ ...inputStyle, width: '100%', whiteSpace: 'pre-wrap', ...sizing }}
    />
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '100%' }}>
      {markdown ? (
        // One height for both panes, set by the outer box's own resize handle, so the source and
        // its preview always line up; each pane scrolls on its own inside it.
        <div
          style={{
            display: 'flex',
            gap: 16,
            width: '100%',
            height: `min(60vh, ${splitHeightEm(initialValue)}em)`,
            minHeight: '8em',
            resize: 'vertical',
            overflow: 'hidden',
          }}
        >
          <div style={{ flex: '1 1 0', minWidth: 0 }}>
            {textarea({ height: '100%', resize: 'none', boxSizing: 'border-box' })}
          </div>
          <div
            style={{
              flex: '1 1 0',
              minWidth: 0,
              border: `1px solid ${tokens.color.border}`,
              borderRadius: 4,
              padding: '4px 8px',
              overflowY: 'auto',
              boxSizing: 'border-box',
            }}
          >
            <Markdown text={value} />
          </div>
        </div>
      ) : (
        textarea({ resize: 'vertical' })
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

// Starting height of the side-by-side editor, from the same estimate at half the width; 60vh
// caps it and the user's drag overrides it.
function splitHeightEm(value: string): number {
  const CHARS_PER_LINE = 45;
  const LINE_EM = 1.7; // the preview's line, which is taller than the textarea's
  const lines = value.split('\n').reduce((n, line) => n + Math.max(1, Math.ceil(line.length / CHARS_PER_LINE)), 0);
  return lines * LINE_EM + 2;
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
