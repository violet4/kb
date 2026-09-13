import { tokens } from '../../shared/tokens';
import type { EventOccurrence } from '../api';
import type { Event } from '../types';

interface OccurrenceChipProps {
  occurrence: EventOccurrence;
  onDoubleClick?: (event: Event) => void;
  recurringColor: string;
  oneTimeColor: string;
}

export default function OccurrenceChip({ occurrence, onDoubleClick, recurringColor, oneTimeColor }: OccurrenceChipProps) {
  const { event, occurs_at } = occurrence;
  const time = event.is_all_day ? '' : formatTime(occurs_at);
  return (
    <div
      title={event.title}
      onDoubleClick={
        onDoubleClick
          ? (e) => {
              e.stopPropagation();
              onDoubleClick(event);
            }
          : undefined
      }
      style={{
        fontSize: 11,
        padding: '2px 4px',
        borderRadius: 3,
        borderLeft: `3px solid ${event.recurrence ? recurringColor : oneTimeColor}`,
        background: tokens.color.background,
        color: tokens.color.text,
        // Wrap and grow with content instead of forcing one truncated line -- the
        // title is the one piece of information a day cell exists to show, so
        // clipping it to fit a fixed line height loses information the cell has
        // room to display if it grows slightly taller.
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        cursor: onDoubleClick ? 'pointer' : undefined,
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
