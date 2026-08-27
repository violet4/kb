import { useState } from 'react';
import { tokens } from '../../shared/tokens';

interface MessageComposerProps {
  onSend: (body: string) => Promise<void>;
  placeholder: string;
}

export default function MessageComposer({ onSend, placeholder }: MessageComposerProps) {
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const trimmed = body.trim();
    if (!trimmed || sending) return;
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
      {error && <p style={{ margin: 0, fontSize: 12, color: tokens.color.danger }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={placeholder}
          rows={2}
          style={{
            flex: 1,
            resize: 'vertical',
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
          disabled={sending || !body.trim()}
          style={{
            alignSelf: 'flex-end',
            padding: '8px 16px',
            borderRadius: 6,
            border: `1px solid ${tokens.color.border}`,
            background: tokens.color.accent,
            color: tokens.color.background,
            fontSize: 13,
            cursor: sending || !body.trim() ? 'default' : 'pointer',
            opacity: sending || !body.trim() ? 0.5 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
