import { tokens } from '../../shared/tokens';
import type { Daily } from '../types';

interface DailyStatusBadgeProps {
  daily: Daily;
}

export default function DailyStatusBadge({ daily }: DailyStatusBadgeProps) {
  const { label, color } = describeStatus(daily);
  return (
    <span style={{ color, fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4 }}>
      {label}
    </span>
  );
}

function describeStatus(daily: Daily): { label: string; color: string } {
  if (daily.is_overdue) return { label: 'overdue', color: tokens.color.overdue };
  if (daily.is_due_now) return { label: 'due', color: tokens.color.due };
  return { label: 'not yet due', color: tokens.color.textMuted };
}
