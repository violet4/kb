interface RowActionButtonProps {
  label: string;
  background: string;
  foreground: string;
  border?: string;
  onClick: () => void;
}

export default function RowActionButton({ label, background, foreground, border, onClick }: RowActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background,
        color: foreground,
        border: border ? `1px solid ${border}` : 'none',
        borderRadius: 4,
        padding: '6px 12px',
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}
