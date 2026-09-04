import type { Event } from '../types';
import EventRow from './EventRow';

interface EventsListProps {
  events: Event[];
  onEventDoubleClick?: (event: Event) => void;
}

export default function EventsList({ events, onEventDoubleClick }: EventsListProps) {
  if (events.length === 0) {
    return <p>Nothing here.</p>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {events.map((event) => (
        <EventRow key={event.id} event={event} onDoubleClick={onEventDoubleClick} />
      ))}
    </div>
  );
}
