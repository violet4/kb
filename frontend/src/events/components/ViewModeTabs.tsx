import { tokens } from '../../shared/tokens';

export type ViewMode = 'list' | 'week' | 'month';

const MODES: { key: ViewMode; label: string }[] = [
  { key: 'list', label: 'List' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
];

interface ViewModeTabsProps {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export default function ViewModeTabs({ mode, onChange }: ViewModeTabsProps) {
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {MODES.map((m) => (
        <ViewModeTab key={m.key} label={m.label} active={m.key === mode} onClick={() => onChange(m.key)} />
      ))}
    </div>
  );
}

function ViewModeTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      style={{
        background: active ? tokens.color.accent : tokens.color.surface,
        color: active ? tokens.color.background : tokens.color.text,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 4,
        padding: '4px 12px',
        fontSize: 13,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}
