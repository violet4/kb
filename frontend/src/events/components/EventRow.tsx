import { tokens } from '../../shared/tokens';
import type { Event } from '../types';

interface EventRowProps {
  event: Event;
  onDoubleClick?: (event: Event) => void;
}

export default function EventRow({ event, onDoubleClick }: EventRowProps) {
  return (
    <div
      onDoubleClick={onDoubleClick ? () => onDoubleClick(event) : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '10px 14px',
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 6,
        cursor: onDoubleClick ? 'pointer' : undefined,
      }}
    >
      <EventRowInfo event={event} />
      <EventRowWhen event={event} />
    </div>
  );
}

function EventRowInfo({ event }: { event: Event }) {
  const place = event.context_name ?? event.tag_name;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontWeight: 500 }}>{event.title}</span>
      <span style={{ fontSize: 12, color: tokens.color.textMuted }}>
        {event.recurrence ? event.recurrence : 'one-off'}
        {place ? ` · ${place}` : ''}
      </span>
    </div>
  );
}

function EventRowWhen({ event }: { event: Event }) {
  const when = formatWhen(event);
  return <span style={{ fontSize: 13, color: tokens.color.text }}>{when}</span>;
}

function formatWhen(event: Event): string {
  const instant = event.next_occurrence ?? event.starts_at;
  const date = new Date(instant);
  if (event.is_all_day) {
    // An all-day Event is stored as UTC midnight on its calendar date (see models.py's
    // Event docstring) -- formatting with the *local* timezone (toLocaleDateString's
    // default) would roll the date back a day for any viewer west of UTC, since local
    // midnight-of-that-date is earlier than the stored UTC instant. timeZone: 'UTC'
    // reads the date components back out the same way they went in.
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
