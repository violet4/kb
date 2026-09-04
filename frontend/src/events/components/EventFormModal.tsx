import { useRef } from 'react';
import Modal from '../../shared/Modal';
import { tokens } from '../../shared/tokens';
import { useEventForm } from '../hooks/useEventForm';
import type { Event } from '../types';
import RecurrenceField from './RecurrenceField';

interface EventFormModalProps {
  /** The calendar date the form is anchored to -- the day double-clicked for a new
   * event, or `existing`'s own date for an edit. null means closed. */
  date: Date | null;
  /** null for "create a new event on `date`"; an Event for "edit this event," seeding
   * every field from it and submitting via PUT instead of POST. */
  existing: Event | null;
  onClose: () => void;
  onSaved: () => void;
}

/** One modal backing both event creation (double-click an empty day) and editing
 * (double-click an existing event) -- the two only differ in what useEventForm seeds
 * and which HTTP verb it submits with, so they share this one form/modal rather than
 * two near-identical copies. date === null means closed, same convention the old
 * NewEventModal used. */
export default function EventFormModal({ date, existing, onClose, onSaved }: EventFormModalProps) {
  // dirtyRef bridges useEventForm's `dirty` flag (only known once EventForm mounts,
  // since it owns the form state) out to Modal's onRequestClose (called on the outer
  // wrapper, before EventForm exists when closed) -- so ESC/backdrop-click can block
  // on unsaved changes without lifting the whole form's state up a level.
  const dirtyRef = useRef(false);

  return (
    <Modal open={date !== null} onClose={onClose} onRequestClose={() => !dirtyRef.current}>
      {date && (
        <EventForm date={date} existing={existing} onClose={onClose} onSaved={onSaved} dirtyRef={dirtyRef} />
      )}
    </Modal>
  );
}

function EventForm({
  date,
  existing,
  onClose,
  onSaved,
  dirtyRef,
}: {
  date: Date;
  existing: Event | null;
  onClose: () => void;
  onSaved: () => void;
  dirtyRef: React.MutableRefObject<boolean>;
}) {
  const form = useEventForm(date, existing, () => {
    onSaved();
    onClose();
  });
  dirtyRef.current = form.dirty;

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        await form.submit();
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 20, width: 380 }}
    >
      <h2 style={{ margin: 0, fontSize: 16 }}>{existing ? 'Edit event' : 'New event'}</h2>
      <TitleField value={form.title} onChange={form.setTitle} />
      <DateTimeFields
        date={form.date}
        onChangeDate={form.setDate}
        time={form.time}
        onChangeTime={form.setTime}
        isAllDay={form.isAllDay}
      />
      <AllDayField checked={form.isAllDay} onChange={form.setIsAllDay} />
      <RecurrenceField field={form.recurrenceField} date={parseDateInput(form.date)} />
      <NotesField value={form.notes} onChange={form.setNotes} />
      {form.error && <p style={{ color: tokens.color.danger, margin: 0, fontSize: 13 }}>{form.error}</p>}
      <ModalActions submitting={form.submitting} onCancel={onClose} submitLabel={existing ? 'Save' : 'Create'} />
    </form>
  );
}

/** Mirrors useEventForm's own parseDateInput/formatDateInput -- kept local rather than
 * exported/shared since this is the only other place a raw "YYYY-MM-DD" field value
 * needs to round-trip through a Date (weekday-naming display, the "t" shortcut below),
 * and duplicating a few lines is cheaper than widening useEventForm's exported surface
 * for one caller. */
function parseDateInput(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatDateInput(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function TitleField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <FormField label="Title">
      <input
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
        placeholder="Event title"
      />
    </FormField>
  );
}

function AllDayField({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      All day
    </label>
  );
}

function DateTimeFields({
  date,
  onChangeDate,
  time,
  onChangeTime,
  isAllDay,
}: {
  date: string;
  onChangeDate: (v: string) => void;
  time: string;
  onChangeTime: (v: string) => void;
  isAllDay: boolean;
}) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div style={{ flex: isAllDay ? 1 : 2 }}>
        <FormField label="Date">
          <input
            type="date"
            value={date}
            onChange={(e) => onChangeDate(e.target.value)}
            onKeyDown={(e) => {
              // "t" for "today" -- a native date input has no digit/arrow-key use for
              // the letter t, so this is safe to intercept unconditionally while the
              // field is focused, mirroring the calendar grid's own "t" shortcut.
              if (e.key === 't') {
                e.preventDefault();
                onChangeDate(formatDateInput(new Date()));
              }
            }}
            style={inputStyle}
          />
        </FormField>
      </div>
      {!isAllDay && (
        <div style={{ flex: 1 }}>
          <FormField label="Time">
            <input type="time" value={time} onChange={(e) => onChangeTime(e.target.value)} style={inputStyle} />
          </FormField>
        </div>
      )}
    </div>
  );
}

function NotesField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <FormField label="Notes">
      <textarea value={value} onChange={(e) => onChange(e.target.value)} style={{ ...inputStyle, resize: 'vertical' }} rows={2} />
    </FormField>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: tokens.color.textMuted }}>
      {label}
      {children}
    </label>
  );
}

function ModalActions({
  submitting,
  onCancel,
  submitLabel,
}: {
  submitting: boolean;
  onCancel: () => void;
  submitLabel: string;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
      <button type="button" onClick={onCancel} style={secondaryButtonStyle}>
        Cancel
      </button>
      <button type="submit" disabled={submitting} style={primaryButtonStyle}>
        {submitting ? `${submitLabel}ing...` : submitLabel}
      </button>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: 4,
  border: `1px solid ${tokens.color.border}`,
  background: tokens.color.background,
  color: tokens.color.text,
  fontSize: 13,
};

const primaryButtonStyle: React.CSSProperties = {
  background: tokens.color.accent,
  color: tokens.color.background,
  border: 'none',
  borderRadius: 4,
  padding: '6px 14px',
  fontSize: 13,
  cursor: 'pointer',
};

const secondaryButtonStyle: React.CSSProperties = {
  background: tokens.color.surface,
  color: tokens.color.text,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  padding: '6px 14px',
  fontSize: 13,
  cursor: 'pointer',
};
