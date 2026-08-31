import Modal from '../../shared/Modal';
import { tokens } from '../../shared/tokens';
import { useNewEventForm } from '../hooks/useNewEventForm';
import RecurrenceField from './RecurrenceField';

interface NewEventModalProps {
  date: Date | null;
  onClose: () => void;
  onCreated: () => void;
}

/** date === null means closed -- the caller passes the double-clicked day's Date to
 * open the modal, and null to close it, so there's one source of truth for both
 * "is it open" and "which day is it creating on" instead of two separate pieces of
 * state that could disagree. */
export default function NewEventModal({ date, onClose, onCreated }: NewEventModalProps) {
  return (
    <Modal open={date !== null} onClose={onClose}>
      {date && <NewEventForm date={date} onClose={onClose} onCreated={onCreated} />}
    </Modal>
  );
}

function NewEventForm({ date, onClose, onCreated }: { date: Date; onClose: () => void; onCreated: () => void }) {
  const form = useNewEventForm(date, () => {
    onCreated();
    onClose();
  });

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        await form.submit();
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 20, width: 380 }}
    >
      <h2 style={{ margin: 0, fontSize: 16 }}>New event on {date.toLocaleDateString()}</h2>
      <TitleField value={form.title} onChange={form.setTitle} />
      <AllDayField checked={form.isAllDay} onChange={form.setIsAllDay} />
      {!form.isAllDay && <TimeField value={form.time} onChange={form.setTime} />}
      <RecurrenceField field={form.recurrenceField} date={date} />
      <NotesField value={form.notes} onChange={form.setNotes} />
      {form.error && <p style={{ color: tokens.color.danger, margin: 0, fontSize: 13 }}>{form.error}</p>}
      <ModalActions submitting={form.submitting} onCancel={onClose} />
    </form>
  );
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

function TimeField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <FormField label="Time">
      <input type="time" value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </FormField>
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

function ModalActions({ submitting, onCancel }: { submitting: boolean; onCancel: () => void }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
      <button type="button" onClick={onCancel} style={secondaryButtonStyle}>
        Cancel
      </button>
      <button type="submit" disabled={submitting} style={primaryButtonStyle}>
        {submitting ? 'Creating...' : 'Create'}
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
