import { tokens } from '../../shared/tokens';
import type { Daily } from '../types';
import DailyStatusBadge from './DailyStatusBadge';
import RowActionButton from './RowActionButton';

interface DailyRowProps {
  daily: Daily;
  onComplete: (id: number) => void;
  onCatchUp: (id: number) => void;
}

export default function DailyRow({ daily, onComplete, onCatchUp }: DailyRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '10px 14px',
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 6,
      }}
    >
      <DailyRowInfo daily={daily} />
      <DailyRowActions daily={daily} onComplete={onComplete} onCatchUp={onCatchUp} />
    </div>
  );
}

function DailyRowInfo({ daily }: { daily: Daily }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontWeight: 500 }}>{daily.description}</span>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <DailyStatusBadge daily={daily} />
        <DailyRowMeta daily={daily} />
      </div>
    </div>
  );
}

function DailyRowMeta({ daily }: { daily: Daily }) {
  const place = daily.context_name ?? daily.tag_name;
  return (
    <span style={{ fontSize: 12, color: tokens.color.textMuted }}>
      due {daily.next_due_date}
      {place ? ` · ${place}` : ''}
    </span>
  );
}

function DailyRowActions({ daily, onComplete, onCatchUp }: DailyRowProps) {
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      {daily.is_overdue && (
        <RowActionButton
          label="Catch up"
          background={tokens.color.surface}
          foreground={tokens.color.overdue}
          border={tokens.color.overdue}
          onClick={() => onCatchUp(daily.id)}
        />
      )}
      <RowActionButton
        label="Complete"
        background={tokens.color.accent}
        foreground={tokens.color.background}
        onClick={() => onComplete(daily.id)}
      />
    </div>
  );
}
