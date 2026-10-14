import { useState, type ReactNode } from 'react';
import { tokens } from '../../shared/tokens';

interface MessageComposerProps {
  onSend: (body: string) => Promise<void>;
  placeholder: string;
  // Ctrl/Cmd+Enter sends, leaving plain Enter for newlines in a multi-line message.
  sendOnModEnter?: boolean;
  // Present while sending is not possible; shown in place of the error and disables Send.
  disabledReason?: string | null;
  // Extra buttons shown beside Send.
  actions?: ReactNode;
}

export default function MessageComposer({
  onSend,
  placeholder,
  sendOnModEnter = false,
  disabledReason = null,
  actions,
}: MessageComposerProps) {
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const trimmed = body.trim();
    if (!trimmed || sending || disabledReason) return;
    setSending(true);
    setError(null);
    try {
      await onSend(trimmed);
      setBody('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        paddingTop: 8,
        borderTop: `1px solid ${tokens.color.border}`,
      }}
    >
      {/* Always rendered, with its line reserved, so a status appearing never moves the textarea. */}
      <p
        style={{
          margin: 0,
          minHeight: 16,
          fontSize: 12,
          color: disabledReason ? tokens.color.textMuted : tokens.color.danger,
        }}
      >
        {disabledReason ?? error}
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        {/* The textarea grows with its message up to maxHeight, then scrolls inside, so the
            content above stays in view. A hidden copy of the text in the same grid cell sets the
            cell's height; measuring the textarea itself would mean collapsing it first, and that
            momentary reflow scrolls the content above. */}
        <div style={{ flex: 1, display: 'grid' }}>
          <div
            aria-hidden
            style={{
              ...textBoxStyle,
              visibility: 'hidden',
              whiteSpace: 'pre-wrap',
              overflow: 'hidden',
            }}
          >
            {body + ' '}
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              const isSendKey = sendOnModEnter ? e.ctrlKey || e.metaKey : !e.shiftKey;
              if (e.key === 'Enter' && isSendKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={placeholder}
            rows={2}
            style={{
              ...textBoxStyle,
              resize: 'none',
              overflowY: 'auto',
              background: tokens.color.surface,
              color: tokens.color.text,
            }}
          />
        </div>
        {/* Stacked, Send at the bottom beside the textarea's last line; buttons share one width. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignSelf: 'flex-end' }}>
          {actions}
          <button
            type="button"
            onClick={handleSend}
            disabled={sending || !body.trim() || !!disabledReason}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: `1px solid ${tokens.color.border}`,
              background: tokens.color.accent,
              color: tokens.color.background,
              fontSize: 13,
              cursor: sending || !body.trim() || !!disabledReason ? 'default' : 'pointer',
              opacity: sending || !body.trim() || !!disabledReason ? 0.5 : 1,
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

// Shared by the textarea and its hidden sizing copy, which must wrap text identically.
const textBoxStyle = {
  gridArea: '1 / 1',
  maxHeight: '40vh',
  boxSizing: 'border-box',
  padding: '8px 10px',
  borderRadius: 6,
  border: `1px solid ${tokens.color.border}`,
  fontSize: 14,
  lineHeight: 1.4,
  fontFamily: 'inherit',
  overflowWrap: 'break-word',
} as const;
