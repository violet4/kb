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
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Dailies</h1>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        <input type="checkbox" checked={dueOnly} onChange={(e) => onToggleDueOnly(e.target.checked)} />
        due only
      </label>
    </div>
  );
}
