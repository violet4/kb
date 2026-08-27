import { tokens } from '../../shared/tokens';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
}

export default function SearchInput({ value, onChange }: SearchInputProps) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Search..."
      autoFocus
      style={{
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 4,
        color: tokens.color.text,
        padding: '8px 12px',
        fontSize: 14,
      }}
    />
  );
}
