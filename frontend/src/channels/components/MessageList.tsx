import { memo, useEffect, useRef } from 'react';
import { tokens } from '../../shared/tokens';
import type { ChannelMessage } from '../types';

interface MessageRowProps {
  message: ChannelMessage;
  isSelf: boolean;
}

// React.memo keyed by the message's own id (via the parent's `key`) means a message row
// already rendered once never re-renders when a poll appends new messages after it -- only
// the newly-appended rows mount. Combined with useChannelMessages' functional merge (which
// never replaces the array, only appends genuinely new entries), this is the actual
// re-render-minimization: React reconciles the existing rows as unchanged by identity and
// skips them, not just "the browser doesn't repaint pixels that didn't move."
const MessageRow = memo(function MessageRow({ message, isSelf }: MessageRowProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '6px 8px' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 12 }}>
        <span style={{ fontWeight: 600, color: isSelf ? tokens.color.accent : tokens.color.text }}>
          {message.from_title || message.from_session}
        </span>
        <span style={{ color: tokens.color.textMuted }}>{new Date(message.created_at).toLocaleString()}</span>
      </div>
      <p style={{ margin: 0, fontSize: 14, whiteSpace: 'pre-wrap', color: tokens.color.text }}>{message.body}</p>
    </div>
  );
});

interface MessageListProps {
  messages: ChannelMessage[];
  selfSessionId: string | null;
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
}

export default function MessageList({
  messages,
  selfSessionId,
  hasMoreOlder,
  loadingOlder,
  onLoadOlder,
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const topSentinelRef = useRef<HTMLDivElement>(null);

  // IntersectionObserver on a sentinel at the top of the scroll container, not a scrollTop
  // threshold check -- fires loadOlder only when the sentinel actually enters view, with no
  // scroll-event listener to throttle/debounce by hand.
  useEffect(() => {
    const sentinel = topSentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root || !hasMoreOlder) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) onLoadOlder();
      },
      { root, threshold: 1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMoreOlder, onLoadOlder]);

  return (
    <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div ref={topSentinelRef} />
      {loadingOlder && (
        <p style={{ margin: 0, padding: 8, textAlign: 'center', fontSize: 12, color: tokens.color.textMuted }}>
          Loading older messages...
        </p>
      )}
      {!hasMoreOlder && messages.length > 0 && (
        <p style={{ margin: 0, padding: 8, textAlign: 'center', fontSize: 11, color: tokens.color.textMuted }}>
          Start of conversation
        </p>
      )}
      {messages.map((message) => (
        <MessageRow key={message.id} message={message} isSelf={message.from_session === selfSessionId} />
      ))}
      {messages.length === 0 && (
        <p style={{ margin: 0, padding: 12, fontSize: 13, color: tokens.color.textMuted }}>No messages yet.</p>
      )}
    </div>
  );
}
