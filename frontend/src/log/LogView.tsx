import { useEffect, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { fetchContextTree } from '../contexts/api';
import { isoDateTime } from '../shared/isoDate';
import { tokens } from '../shared/tokens';
import { usePolling } from '../shared/usePolling';
import { createLogEntry, fetchRecentLog } from './api';
import ContextPicker from './components/ContextPicker';
import type { LogItem } from './types';

const POLL_SECONDS = 15;
const DEFAULT_CONTEXT = 'inbox';

export default function LogView() {
  const { data: entries, error: listError, refresh } = usePolling(fetchRecentLog, POLL_SECONDS);
  const { data: tree, error: treeError } = usePolling(fetchContextTree, 60);

  const [body, setBody] = useState('');
  const [contextId, setContextId] = useState<number | null>(null);
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<{ kind: 'error' | 'ok'; text: string } | null>(null);

  // Default to `inbox` once the tree arrives, unless the user already picked something.
  useEffect(() => {
    if (touched || !tree) return;
    const inbox = tree.find((c) => c.name === DEFAULT_CONTEXT);
    if (inbox) setContextId(inbox.id);
  }, [tree, touched]);

  const canSubmit = body.trim() !== '' && contextId !== null && !submitting;

  const submit = async () => {
    if (!canSubmit || contextId === null) return;
    setSubmitting(true);
    try {
      const created = await createLogEntry(body.trim(), contextId);
      setBody('');
      setStatus({ kind: 'ok', text: `Logged #${created.id}` });
      refresh();
    } catch (e) {
      setStatus({ kind: 'error', text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSubmitting(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void submit();
    }
  };

  const message =
    status ??
    (treeError ? { kind: 'error' as const, text: treeError } : null) ??
    (tree && contextId === null ? { kind: 'error' as const, text: 'Pick a context from the list.' } : null);

  return (
    <main style={{ padding: '16px 24px', maxWidth: 900 }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <textarea
          value={body}
          autoFocus
          rows={4}
          placeholder="What happened? (Ctrl+Enter to log)"
          onChange={(e) => {
            setBody(e.target.value);
            setStatus(null);
          }}
          onKeyDown={onKeyDown}
          style={{
            background: tokens.color.surface,
            color: tokens.color.text,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 4,
            padding: 8,
            fontSize: 14,
            fontFamily: 'inherit',
            resize: 'vertical',
          }}
        />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {tree ? (
            <ContextPicker
              nodes={tree}
              selectedId={contextId}
              onChange={(id) => {
                setTouched(true);
                setContextId(id);
              }}
            />
          ) : (
            <span style={{ width: 260, fontSize: 13, color: tokens.color.textMuted }}>loading contexts…</span>
          )}
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!canSubmit}
            style={{
              background: canSubmit ? tokens.color.accent : tokens.color.border,
              color: canSubmit ? '#fff' : tokens.color.textMuted,
              border: 'none',
              borderRadius: 4,
              padding: '6px 16px',
              fontSize: 13,
              cursor: canSubmit ? 'pointer' : 'default',
            }}
          >
            {submitting ? 'Logging…' : 'Log'}
          </button>
        </div>
        {/* Fixed-height slot so a status/error message never shifts the list below. */}
        <div
          style={{
            minHeight: 18,
            fontSize: 12,
            color: message?.kind === 'error' ? tokens.color.danger : tokens.color.textMuted,
          }}
        >
          {message?.text}
        </div>
      </section>

      <section style={{ marginTop: 8 }}>
        {listError && <p style={{ color: tokens.color.danger, fontSize: 12 }}>{listError}</p>}
        {entries && entries.length === 0 && <p style={{ color: tokens.color.textMuted }}>No log entries yet.</p>}
        {entries?.map((e) => (
          <LogRow key={e.id} entry={e} />
        ))}
      </section>
    </main>
  );
}

function LogRow({ entry }: { entry: LogItem }) {
  return (
    <div style={{ padding: '8px 0', borderBottom: `1px solid ${tokens.color.border}` }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 12 }}>
        <span style={{ color: tokens.color.textMuted, fontVariantNumeric: 'tabular-nums' }}>
          {isoDateTime(entry.occurred_at_utc)}
        </span>
        {entry.context && (
          <Link
            to={`/contexts/${entry.context.id}`}
            style={{
              ...tokens.link,
              border: `1px solid ${tokens.color.border}`,
              borderRadius: 10,
              padding: '0 8px',
            }}
          >
            {entry.context.name}
          </Link>
        )}
        {entry.domain && <span style={{ color: tokens.color.textMuted }}>{entry.domain}</span>}
      </div>
      <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 14, marginTop: 4 }}>{entry.body}</div>
    </div>
  );
}


