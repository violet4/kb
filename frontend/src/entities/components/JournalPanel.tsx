import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { isoDateTime } from '../../shared/isoDate';
import { tokens } from '../../shared/tokens';
import type { JournalEntry } from '../types';

interface JournalPanelProps {
  entries: JournalEntry[];
}

export default function JournalPanel({ entries }: JournalPanelProps) {
  if (entries.length === 0) return null;
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h2 style={{ margin: 0, fontSize: 15 }}>Journal</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {entries.map((entry) => (
          <JournalEntryRow key={entry.id} entry={entry} />
        ))}
      </div>
    </section>
  );
}

const ACTION_LABELS: Record<JournalEntry['action'], string | null> = {
  create: 'created',
  read: 'read',
  update: null, // the field change itself says it
  delete: 'deleted',
  note: null,
};

// subject: which record the entry is about, for a list mixing several records' entries.
export function JournalEntryRow({ entry, subject }: { entry: JournalEntry; subject?: ReactNode }) {
  const when = isoDateTime(entry.created_at_utc);
  const label = ACTION_LABELS[entry.action];
  return (
    <div style={{ fontSize: 13, borderLeft: `2px solid ${tokens.color.border}`, paddingLeft: 10 }}>
      <p style={{ margin: 0, color: tokens.color.textMuted, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <span>{when}</span>
        {subject}
        {entry.session_id && (
          <Link to={`/agents/${entry.session_id}`} style={tokens.link} title={entry.session_id}>
            session {entry.session_id.slice(0, 8)}
          </Link>
        )}
      </p>
      {label && <p style={{ margin: '2px 0 0' }}>{label}</p>}
      {entry.field && (
        <p style={{ margin: '2px 0 0' }}>
          <strong>{entry.field}</strong>: {entry.old_value ?? '∅'} → {entry.new_value ?? '∅'}
        </p>
      )}
      {entry.note && <p style={{ margin: '2px 0 0' }}>{entry.note}</p>}
    </div>
  );
}
