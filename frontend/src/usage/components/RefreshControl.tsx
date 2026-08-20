import { useEffect, useState } from 'react';
import { tokens } from '../../shared/tokens';

interface RefreshControlProps {
  lastUpdatedAt: number | null;
  nextRefreshAt: number | null;
  onRefresh: () => void;
}

export default function RefreshControl({ lastUpdatedAt, nextRefreshAt, onRefresh }: RefreshControlProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const sinceLabel = lastUpdatedAt !== null ? `updated ${formatSeconds((now - lastUpdatedAt) / 1000)} ago` : null;
  const untilLabel =
    nextRefreshAt !== null ? `next refresh in ${formatSeconds(Math.max(0, nextRefreshAt - now) / 1000)}` : null;

  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 12, color: tokens.color.textMuted }}>
      <button
        type="button"
        onClick={onRefresh}
        style={{
          padding: '4px 10px',
          borderRadius: 6,
          border: `1px solid ${tokens.color.border}`,
          background: tokens.color.surface,
          color: tokens.color.text,
          fontSize: 12,
          cursor: 'pointer',
        }}
      >
        Refresh
      </button>
      {sinceLabel && <span>{sinceLabel}</span>}
      {untilLabel && <span>· {untilLabel}</span>}
    </div>
  );
}

function formatSeconds(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}
