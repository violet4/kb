import { useEffect, useState } from 'react';
import { tokens } from '../../shared/tokens';
import { formatCountdown, formatResetsAtTooltip } from '../formatCountdown';

interface UsageBarProps {
  label: string;
  pct: number;
  resetsAt: string;
  periodMs: number;
}

export default function UsageBar({ label, pct, resetsAt, periodMs }: UsageBarProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(interval);
  }, []);

  const clamped = Math.max(0, Math.min(100, pct));
  const resetsAtMs = new Date(resetsAt).getTime();
  const remainingMs = Math.max(0, resetsAtMs - now);
  const elapsedMs = Math.max(0, Math.min(periodMs, periodMs - remainingMs));
  const estimatedPct = Math.max(0, Math.min(100, (elapsedMs / periodMs) * 100));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span style={{ color: tokens.color.textMuted }}>
          {pct}% used ·{' '}
          <span title={formatResetsAtTooltip(resetsAt)} style={{ cursor: 'default', textDecoration: 'underline dotted' }}>
            {formatCountdown(remainingMs)} left
          </span>
        </span>
      </div>
      <div
        style={{
          position: 'relative',
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
        <div
          title={`Estimated pace: ${estimatedPct.toFixed(0)}% by now if used evenly across the period`}
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${estimatedPct}%`,
            width: 2,
            background: tokens.color.text,
            opacity: 0.6,
            transform: 'translateX(-1px)',
          }}
        />
      </div>
    </div>
  );
}
