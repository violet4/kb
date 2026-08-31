import { tokens } from '../../shared/tokens';
import type { EventOccurrence } from '../api';

interface OccurrenceChipProps {
  occurrence: EventOccurrence;
}

export default function OccurrenceChip({ occurrence }: OccurrenceChipProps) {
  const { event, occurs_at } = occurrence;
  const time = event.is_all_day ? '' : formatTime(occurs_at);
  return (
    <div
      title={event.title}
      style={{
        fontSize: 11,
        padding: '2px 4px',
        borderRadius: 3,
        background: tokens.color.background,
        color: tokens.color.text,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {time && <span style={{ color: tokens.color.textMuted }}>{time} </span>}
      {event.title}
    </div>
  );
}

function formatTime(instant: string): string {
  return new Date(instant).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}
