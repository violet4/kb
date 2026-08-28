import { tokens } from '../../shared/tokens';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export default function SearchInput({ value, onChange, onSubmit }: SearchInputProps) {
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSubmit();
        }}
        placeholder="Search..."
        autoFocus
        style={{
          flex: 1,
          background: tokens.color.surface,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          color: tokens.color.text,
          padding: '8px 12px',
          fontSize: 14,
        }}
      />
      <button
        type="button"
        onClick={onSubmit}
        style={{
          background: tokens.color.surface,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          color: tokens.color.text,
          padding: '8px 16px',
          fontSize: 14,
          cursor: 'pointer',
        }}
      >
        Search
      </button>
    </div>
  );
}
