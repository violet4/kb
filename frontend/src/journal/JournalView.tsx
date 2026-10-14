import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { JournalEntryRow } from '../entities/components/JournalPanel';
import { entityPath } from '../entities/navigation';
import type { EntityType } from '../entities/types';
import { pageTitle, useDocumentTitle } from '../shared/useDocumentTitle';
import { tokens } from '../shared/tokens';
import { fetchTimeline } from './api';
import type { TimelineEntry } from './types';

const linkButton = { ...tokens.link, background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 13 } as const;

// Every record's history in one timeline, newest first, a page at a time. Reads are off by
// default: they say who looked, not what changed, and they outnumber everything else.
export default function JournalView() {
  useDocumentTitle(pageTitle('journal', 'Journal'));
  const [includeReads, setIncludeReads] = useState(false);
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (before: number | null) => {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchTimeline(before, includeReads);
      setEntries((prev) => (before === null ? page.entries : [...prev, ...page.entries]));
      setNextBefore(page.next_before);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };
  // Back to the newest page whenever the filter changes.
  useEffect(() => void load(null), [includeReads]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Journal</h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={includeReads} onChange={(e) => setIncludeReads(e.target.checked)} />
          include reads
        </label>
        <button style={linkButton} onClick={() => load(null)} disabled={loading}>
          refresh
        </button>
      </div>
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {entries.map((entry) => (
          <JournalEntryRow key={entry.id} entry={entry} subject={<Subject entry={entry} />} />
        ))}
      </div>
      <div style={{ minHeight: 20, fontSize: 13, color: tokens.color.textMuted }}>
        {loading ? (
          'Loading…'
        ) : nextBefore !== null ? (
          <button style={linkButton} onClick={() => load(nextBefore)}>
            load older
          </button>
        ) : (
          entries.length > 0 && 'start of history'
        )}
      </div>
    </div>
  );
}

// The record an entry is about: its current title, linked to its page when it has one.
function Subject({ entry }: { entry: TimelineEntry }) {
  const ref = `${entry.entity_type}:${entry.entity_id}`;
  const { record } = entry;
  if (!record) return <span>{ref}</span>;
  const text = `${ref} ${record.label}`;
  if (!record.drilldown) return <span style={{ color: tokens.color.text }}>{text}</span>;
  return (
    <Link to={entityPath(record.type as EntityType, record.id)} style={tokens.link}>
      {text}
    </Link>
  );
}
