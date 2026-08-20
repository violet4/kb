import { tokens } from '../../shared/tokens';

interface UsageBarProps {
  label: string;
  pct: number;
  resets: string;
}

export default function UsageBar({ label, pct, resets }: UsageBarProps) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span style={{ color: tokens.color.textMuted }}>
          {pct}% used · resets {resets}
        </span>
      </div>
      <div
        style={{
          height: 14,
          borderRadius: 7,
          background: tokens.color.barTrack,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${clamped}%`,
            height: '100%',
            background: tokens.color.barFill,
            borderRadius: 7,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  );
}
