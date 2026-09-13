import { useState } from 'react';
import { createEvent, deleteEvent, updateEvent } from '../api';
import type { Event } from '../types';
import { useRecurrenceField } from './useRecurrenceField';

interface UseEventFormResult {
  title: string;
  setTitle: (value: string) => void;
  date: string;
  setDate: (value: string) => void;
  time: string;
  setTime: (value: string) => void;
  isAllDay: boolean;
  setIsAllDay: (value: boolean) => void;
  recurrenceField: ReturnType<typeof useRecurrenceField>;
  notes: string;
  setNotes: (value: string) => void;
  submitting: boolean;
  error: string | null;
  dirty: boolean;
  submit: () => Promise<boolean>;
  deleting: boolean;
  remove: () => Promise<boolean>;
}

/** Local form state plus submit logic for creating or editing an Event -- `initialDate`
 * seeds the date field (the day double-clicked, or `existing`'s own date for an edit),
 * but the date is itself an editable field like time, not a fixed prop, so a
 * double-clicked or wrong day can be corrected without cancelling and re-opening on the
 * right day. Passing `existing` seeds every other field from that Event and submits via
 * PUT instead of POST, so NewEventModal/EditEventModal share one form implementation
 * rather than two parallel copies (kb instructions #1, single owner per concept).
 * `dirty` is true once any field differs from its initial value, so a caller can block a
 * quick ESC-close on unsaved changes (see Modal). */
export function useEventForm(initialDate: Date, existing: Event | null, onSaved: () => void): UseEventFormResult {
  const initial = initialFieldsFor(initialDate, existing);
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [isAllDay, setIsAllDay] = useState(initial.isAllDay);
  const recurrenceField = useRecurrenceField(parseDateInput(date), initial.recurrence);
  const [notes, setNotes] = useState(initial.notes);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    title !== initial.title ||
    date !== initial.date ||
    time !== initial.time ||
    isAllDay !== initial.isAllDay ||
    recurrenceField.rrule !== initial.recurrence ||
    notes !== initial.notes;

  const submit = async (): Promise<boolean> => {
    if (!title.trim()) {
      setError('Title is required.');
      return false;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        starts_at: composeStartsAt(parseDateInput(date), time, isAllDay),
        is_all_day: isAllDay,
        recurrence: recurrenceField.rrule.trim() || null,
        notes: notes.trim() || null,
      };
      if (existing) await updateEvent(existing.id, payload);
      else await createEvent(payload);
      onSaved();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (): Promise<boolean> => {
    if (!existing) return false;
    setDeleting(true);
    setError(null);
    try {
      await deleteEvent(existing.id);
      onSaved();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setDeleting(false);
    }
  };

  return {
    title,
    setTitle,
    date,
    setDate,
    time,
    setTime,
    isAllDay,
    setIsAllDay,
    recurrenceField,
    notes,
    setNotes,
    submitting,
    error,
    dirty,
    submit,
    deleting,
    remove,
  };
}

interface InitialFields {
  title: string;
  date: string;
  time: string;
  isAllDay: boolean;
  recurrence: string;
  notes: string;
}

function initialFieldsFor(initialDate: Date, existing: Event | null): InitialFields {
  if (!existing) {
    return {
      title: '',
      date: formatDateInput(initialDate),
      time: formatTimeInput(initialDate),
      isAllDay: false,
      recurrence: '',
      notes: '',
    };
  }
  const startsAt = new Date(existing.starts_at);
  return {
    title: existing.title,
    // An all-day starts_at is UTC midnight on the intended calendar date (see
    // models.py's Event docstring) -- read it back with UTC getters, not local ones,
    // or a viewer whose local zone is offset from UTC sees the previous/next day
    // (the exact bug this comment documents: re-saving an all-day event, or toggling
    // an existing timed event to all-day, shifted its date by one).
    date: existing.is_all_day ? formatDateInputUtc(startsAt) : formatDateInput(startsAt),
    time: existing.is_all_day ? '09:00' : formatTimeInput(startsAt),
    isAllDay: existing.is_all_day,
    recurrence: existing.recurrence ?? '',
    notes: existing.notes ?? '',
  };
}

function formatDateInput(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateInputUtc(date: Date): string {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`;
}

function formatTimeInput(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

/** Parses a <input type="date"> value ("YYYY-MM-DD") back into a local-midnight Date --
 * the inverse of formatDateInput, and the shape composeStartsAt/useRecurrenceField
 * expect (a Date whose year/month/date components are what matters, time-of-day
 * ignored). */
function parseDateInput(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
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
