import type { Daily } from '../types';
import DailyRow from './DailyRow';

interface DailiesListProps {
  dailies: Daily[];
  onComplete: (id: number) => void;
  onCatchUp: (id: number) => void;
}

export default function DailiesList({ dailies, onComplete, onCatchUp }: DailiesListProps) {
  if (dailies.length === 0) {
    return <p>Nothing here.</p>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {dailies.map((daily) => (
        <DailyRow key={daily.id} daily={daily} onComplete={onComplete} onCatchUp={onCatchUp} />
      ))}
    </div>
  );
}
