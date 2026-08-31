import { tokens } from '../../shared/tokens';

interface CalendarNavProps {
  label: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
}

export default function CalendarNav({ label, onPrev, onNext, onToday }: CalendarNavProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <NavButton onClick={onPrev} label="Previous">
        ‹
      </NavButton>
      <NavButton onClick={onToday} label="Jump to today">
        Today
      </NavButton>
      <NavButton onClick={onNext} label="Next">
        ›
      </NavButton>
      <span style={{ fontSize: 14, fontWeight: 500 }}>{label}</span>
    </div>
  );
}

function NavButton({ onClick, label, children }: { onClick: () => void; label: string; children: string }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      style={{
        background: tokens.color.surface,
        color: tokens.color.text,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 4,
        padding: '4px 10px',
        fontSize: 13,
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  );
}
