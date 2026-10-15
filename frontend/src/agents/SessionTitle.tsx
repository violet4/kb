import { useEffect, useState } from 'react';
import { tokens } from '../shared/tokens';

interface SessionTitleProps {
  title: string;
  sessionId: string;
  // Absent when the session is not live, which leaves the title read-only.
  onRename?: (title: string) => Promise<void>;
  // Why a rename can't be sent now (from the server), or null when it can.
  renameBlocker?: string | null;
}

// How long a submitted title shows before the polled one replaces it, so a rename the session
// dropped reverts on screen instead of displaying as if it had applied.
const PENDING_TIMEOUT_MS = 10_000;

// The agent page's heading. Double-click opens an input; Enter sends the new title as
// `/rename` to the session, Escape or leaving the input cancels. The session writes the new
// title to its transcript, so the submitted title shows muted until the polled one changes.
export default function SessionTitle({ title, sessionId, onRename, renameBlocker = null }: SessionTitleProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setPending(null), [title]);
  useEffect(() => {
    if (pending === null) return;
    const timer = setTimeout(() => setPending(null), PENDING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [pending]);

  const canRename = onRename !== undefined && renameBlocker === null;

  async function submit() {
    if (draft === null || !onRename) return;
    const next = draft.trim();
    if (!next || next === title) {
      setDraft(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onRename(next);
      setPending(next);
      setDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function cancel() {
    setDraft(null);
    setError(null);
  }

  if (draft !== null) {
    return (
      <input
        autoFocus
        value={draft}
        disabled={busy}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => !busy && cancel()}
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing) return;
          if (e.key === 'Enter') {
            e.preventDefault();
            submit();
          } else if (e.key === 'Escape') {
            // Marks the event handled, so the page's Escape-interrupts-the-session listener skips it.
            e.preventDefault();
            cancel();
          }
        }}
        title={error ?? 'Enter to rename, Escape to cancel'}
        aria-label="Session title"
        style={{
          ...headingStyle,
          flex: 1,
          padding: '0 4px',
          border: `1px solid ${error ? tokens.color.danger : tokens.color.border}`,
          borderRadius: 4,
          background: 'transparent',
          color: tokens.color.text,
        }}
      />
    );
  }

  return (
    <h1
      onDoubleClick={canRename ? () => setDraft(pending ?? title) : undefined}
      title={canRename ? `${sessionId}\nDouble-click to rename` : renameBlocker ? `${sessionId}\n${renameBlocker}` : sessionId}
      style={{
        ...headingStyle,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        cursor: canRename ? 'text' : undefined,
        color: pending !== null ? tokens.color.textMuted : undefined,
      }}
    >
      {pending ?? title}
    </h1>
  );
}

const headingStyle = { margin: 0, minWidth: 0, fontSize: 18, fontFamily: 'monospace' } as const;
