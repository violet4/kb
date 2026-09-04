import { useState } from 'react';
import type { Event } from '../types';

interface EventFormModalState {
  date: Date | null;
  existing: Event | null;
  openForNewEvent: (date: Date) => void;
  openForEdit: (event: Event) => void;
  close: () => void;
}

/** Shared open/close state for EventFormModal, driving both "double-click an empty
 * day/slot" (create) and "double-click an existing event" (edit) from MonthView,
 * WeekView, and EventsList -- one small hook instead of each caller hand-rolling its
 * own two-piece (date, existing) state pair. */
export function useEventFormModalState(): EventFormModalState {
  const [date, setDate] = useState<Date | null>(null);
  const [existing, setExisting] = useState<Event | null>(null);

  return {
    date,
    existing,
    openForNewEvent: (d) => {
      setExisting(null);
      setDate(d);
    },
    openForEdit: (event) => {
      setExisting(event);
      setDate(new Date(event.starts_at));
    },
    close: () => setDate(null),
  };
}
