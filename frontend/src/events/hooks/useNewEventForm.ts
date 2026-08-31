import { useState } from 'react';
import { createEvent } from '../api';
import { useRecurrenceField } from './useRecurrenceField';

interface UseNewEventFormResult {
  title: string;
  setTitle: (value: string) => void;
  time: string;
  setTime: (value: string) => void;
  isAllDay: boolean;
  setIsAllDay: (value: boolean) => void;
  recurrenceField: ReturnType<typeof useRecurrenceField>;
  notes: string;
  setNotes: (value: string) => void;
  submitting: boolean;
  error: string | null;
  submit: () => Promise<boolean>;
}

/** Local form state plus submit logic for creating an Event on a specific calendar
 * date -- `date` is fixed (the day the user double-clicked), only the time-of-day and
 * other fields are editable. Resets to blank defaults each time `date` changes, so
 * reopening the modal on a different day doesn't carry over the previous day's draft. */
export function useNewEventForm(date: Date, onCreated: () => void): UseNewEventFormResult {
  const [title, setTitle] = useState('');
  const [time, setTime] = useState('09:00');
  const [isAllDay, setIsAllDay] = useState(false);
  const recurrenceField = useRecurrenceField(date);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (): Promise<boolean> => {
    if (!title.trim()) {
      setError('Title is required.');
      return false;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createEvent({
        title: title.trim(),
        starts_at: composeStartsAt(date, time, isAllDay),
        is_all_day: isAllDay,
        recurrence: recurrenceField.rrule.trim() || null,
        notes: notes.trim() || null,
      });
      onCreated();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  return {
    title,
    setTitle,
    time,
    setTime,
    isAllDay,
    setIsAllDay,
    recurrenceField,
    notes,
    setNotes,
    submitting,
    error,
    submit,
  };
}

/** For an all-day event, UTC midnight on `date`'s calendar date (see models.py's Event
 * docstring -- the same convention kb_cli/event.py's _parse_starts_at applies for
 * --all-day). For a timed event, `date` combined with the picked local time,
 * converted to UTC. */
function composeStartsAt(date: Date, time: string, isAllDay: boolean): string {
  if (isAllDay) {
    return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())).toISOString();
  }
  const [hours, minutes] = time.split(':').map(Number);
  const local = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes);
  return local.toISOString();
}
