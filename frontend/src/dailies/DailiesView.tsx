import { useState } from 'react';
import { tokens } from '../shared/tokens';
import DailiesList from './components/DailiesList';
import { useDailies } from './hooks/useDailies';

export default function DailiesView() {
  const [dueOnly, setDueOnly] = useState(true);
  const { dailies, loading, error, complete, catchUp } = useDailies(dueOnly);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <DailiesHeader dueOnly={dueOnly} onToggleDueOnly={setDueOnly} />
      {loading && <p style={{ color: tokens.color.textMuted }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && <DailiesList dailies={dailies} onComplete={complete} onCatchUp={catchUp} />}
    </div>
  );
}

function DailiesHeader({ dueOnly, onToggleDueOnly }: { dueOnly: boolean; onToggleDueOnly: (v: boolean) => void }) {
  const now = new Date();
  const dateStr = now.toLocaleDateString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit' });
  const timeStr = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  const week = getIsoWeek(now);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <p style={{ margin: 0, fontSize: 13, color: tokens.color.textMuted }}>
        {dateStr} {timeStr} (week {week})
      </p>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Dailies</h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={dueOnly} onChange={(e) => onToggleDueOnly(e.target.checked)} />
          due only
        </label>
      </div>
    </div>
  );
}

function getIsoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}
