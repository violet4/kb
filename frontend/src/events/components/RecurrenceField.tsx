import { tokens } from '../../shared/tokens';
import { describeRrule, PRESET_LABELS } from '../recurrencePresets';
import type { useRecurrenceField } from '../hooks/useRecurrenceField';

interface RecurrenceFieldProps {
  field: ReturnType<typeof useRecurrenceField>;
  date: Date;
}

export default function RecurrenceField({ field, date }: RecurrenceFieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <RecurrenceLabel />
      <PresetSelect value={field.preset} onChange={field.setPreset} />
      {field.preset === 'every-n-days' && <EveryNInput value={field.everyN} onChange={field.setEveryN} />}
      <RawRruleInput value={field.rrule} onChange={field.setRruleDirect} />
      <RecurrenceDescription rrule={field.rrule} date={date} />
      <RecurrenceHelp />
    </div>
  );
}

function RecurrenceLabel() {
  return <span style={{ fontSize: 13, color: tokens.color.textMuted }}>Recurrence</span>;
}

function PresetSelect({
  value,
  onChange,
}: {
  value: ReturnType<typeof useRecurrenceField>['preset'];
  onChange: ReturnType<typeof useRecurrenceField>['setPreset'];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as ReturnType<typeof useRecurrenceField>['preset'])}
      style={selectStyle}
    >
      {PRESET_LABELS.map((p) => (
        <option key={p.value} value={p.value}>
          {p.label}
        </option>
      ))}
    </select>
  );
}

function EveryNInput({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
      Every
      <input
        type="number"
        min={1}
        value={value}
        onChange={(e) => onChange(Math.max(1, Number(e.target.value)))}
        style={{ ...inputStyle, width: 60 }}
      />
      days
    </label>
  );
}

function RawRruleInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ ...inputStyle, fontFamily: 'monospace' }}
      placeholder="Raw RRULE, e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR"
    />
  );
}

function RecurrenceDescription({ rrule, date }: { rrule: string; date: Date }) {
  return <span style={{ fontSize: 12, color: tokens.color.textMuted }}>{describeRrule(rrule, date)}</span>;
}

function RecurrenceHelp() {
  return (
    <details style={{ fontSize: 12, color: tokens.color.textMuted }}>
      <summary style={{ cursor: 'pointer' }}>What is RRULE?</summary>
      <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <p style={{ margin: 0 }}>
          RRULE is the recurrence-rule format from RFC 5545 (iCalendar), the same standard behind Google Calendar,
          Outlook, and most calendar apps. A rule is a semicolon-separated list of parts, e.g.{' '}
          <code>FREQ=WEEKLY;BYDAY=MO,WE,FR</code> for &quot;every Monday, Wednesday, and Friday.&quot;
        </p>
        <p style={{ margin: 0 }}>
          Common parts: <code>FREQ</code> (DAILY/WEEKLY/MONTHLY/YEARLY), <code>INTERVAL</code> (every N periods),{' '}
          <code>BYDAY</code> (MO/TU/WE/TH/FR/SA/SU), <code>BYMONTHDAY</code>, <code>BYMONTH</code>,{' '}
          <code>COUNT</code> (stop after N occurrences), <code>UNTIL</code> (stop after a date).
        </p>
        <a
          href="https://datatracker.ietf.org/doc/html/rfc5545#section-3.3.10"
          target="_blank"
          rel="noreferrer"
          style={tokens.link}
        >
          Full RRULE spec (RFC 5545 §3.3.10)
        </a>
      </div>
    </details>
  );
}

const selectStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: 4,
  border: `1px solid ${tokens.color.border}`,
  background: tokens.color.background,
  color: tokens.color.text,
  fontSize: 13,
};

const inputStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: 4,
  border: `1px solid ${tokens.color.border}`,
  background: tokens.color.background,
  color: tokens.color.text,
  fontSize: 13,
};
