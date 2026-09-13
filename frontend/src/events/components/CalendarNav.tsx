import { tokens } from '../../shared/tokens';

interface CalendarNavProps {
  label: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  /** Centers the label across the full nav width at a larger size, for a view (e.g.
   * MonthView) that wants its date label to read as a page heading rather than a small
   * caption next to the nav buttons. Default keeps the original inline, left-aligned
   * layout (e.g. WeekView's date-range label). */
  centerLabel?: boolean;
}

export default function CalendarNav({ label, onPrev, onNext, onToday, centerLabel }: CalendarNavProps) {
  const buttons = (
    <>
      <NavButton onClick={onPrev} label="Previous">
        ‹
      </NavButton>
      <NavButton onClick={onToday} label="Jump to today">
        Today
      </NavButton>
      <NavButton onClick={onNext} label="Next">
        ›
      </NavButton>
    </>
  );

  if (centerLabel) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12 }}>{buttons}</div>
        <span style={{ fontSize: 20, fontWeight: 600, textAlign: 'center' }}>{label}</span>
        <div />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {buttons}
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
