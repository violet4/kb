import { useLayoutEffect, useRef, useState } from 'react';
import { tokens } from '../../shared/tokens';

interface MessageComposerProps {
  onSend: (body: string) => Promise<void>;
  placeholder: string;
  // Ctrl/Cmd+Enter sends, leaving plain Enter for newlines in a multi-line message.
  sendOnModEnter?: boolean;
  // Present while sending is not possible; shown in place of the error and disables Send.
  disabledReason?: string | null;
}

export default function MessageComposer({
  onSend,
  placeholder,
  sendOnModEnter = false,
  disabledReason = null,
}: MessageComposerProps) {
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow with the message up to maxHeight, then scroll inside, so the content above stays in view.
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight + textarea.offsetHeight - textarea.clientHeight}px`;
  }, [body]);

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 8, borderTop: `1px solid ${tokens.color.border}` }}>
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
        <textarea
          ref={textareaRef}
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
            flex: 1,
            resize: 'none',
            maxHeight: '40vh',
            overflowY: 'auto',
            boxSizing: 'border-box',
            padding: '8px 10px',
            borderRadius: 6,
            border: `1px solid ${tokens.color.border}`,
            background: tokens.color.surface,
            color: tokens.color.text,
            fontSize: 14,
            fontFamily: 'inherit',
          }}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sending || !body.trim() || !!disabledReason}
          style={{
            alignSelf: 'flex-end',
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
  );
}
