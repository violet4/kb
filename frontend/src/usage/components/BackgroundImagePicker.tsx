import { useState } from 'react';
import { tokens } from '../../shared/tokens';

interface BackgroundImagePickerProps {
  value: string;
  onChange: (value: string) => void;
}

export default function BackgroundImagePicker({ value, onChange }: BackgroundImagePickerProps) {
  const [draft, setDraft] = useState(value);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onChange(draft.trim());
      }}
      style={{ display: 'flex', gap: 8, alignItems: 'center' }}
    >
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Background image: filepath or URL"
        style={{
          flex: 1,
          padding: '6px 10px',
          borderRadius: 6,
          border: `1px solid ${tokens.color.border}`,
          background: tokens.color.surface,
          color: tokens.color.text,
          fontSize: 13,
        }}
      />
      <button
        type="submit"
        style={{
          padding: '6px 12px',
          borderRadius: 6,
          border: `1px solid ${tokens.color.border}`,
          background: tokens.color.surface,
          color: tokens.color.text,
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        Set
      </button>
      {value && (
        <button
          type="button"
          onClick={() => {
            setDraft('');
            onChange('');
          }}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            border: `1px solid ${tokens.color.border}`,
            background: 'transparent',
            color: tokens.color.textMuted,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Clear
        </button>
      )}
    </form>
  );
}
