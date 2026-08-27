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

function JournalEntryRow({ entry }: { entry: JournalEntry }) {
  const when = new Date(entry.created_at).toLocaleString();
  return (
    <div style={{ fontSize: 13, borderLeft: `2px solid ${tokens.color.border}`, paddingLeft: 10 }}>
      <p style={{ margin: 0, color: tokens.color.textMuted }}>{when}</p>
      {entry.field && (
        <p style={{ margin: '2px 0 0' }}>
          <strong>{entry.field}</strong>: {entry.old_value ?? '∅'} → {entry.new_value ?? '∅'}
        </p>
      )}
      {entry.note && <p style={{ margin: '2px 0 0' }}>{entry.note}</p>}
    </div>
  );
}
