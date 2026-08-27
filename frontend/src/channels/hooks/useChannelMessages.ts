import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchChannelMessages } from '../api';
import type { ChannelMessage } from '../types';

interface UseChannelMessagesResult {
  messages: ChannelMessage[]; // oldest first, ready to render top-to-bottom
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  error: string | null;
  loadOlder: () => void;
}

const PAGE_SIZE = 50;
const POLL_INTERVAL_SECONDS = 5;

// Appends newly-polled messages via a functional update keyed by id (never replaces the
// whole array) so React only creates elements for genuinely new messages -- existing
// MessageRow elements keep their identity and don't re-render. See MessageList's own
// React.memo wrapper for the other half of this: a stable id-keyed element still needs the
// component itself to skip re-rendering on an unrelated parent state change.
function mergeNew(prev: ChannelMessage[], incoming: ChannelMessage[]): ChannelMessage[] {
  const knownIds = new Set(prev.map((m) => m.id));
  const fresh = incoming.filter((m) => !knownIds.has(m.id));
  if (fresh.length === 0) return prev;
  return [...prev, ...fresh].sort((a, b) => a.id - b.id);
}

export function useChannelMessages(channelId: number | null): UseChannelMessagesResult {
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const oldestIdRef = useRef<number | null>(null);

  useEffect(() => {
    setMessages([]);
    setHasMoreOlder(false);
    setError(null);
    if (channelId === null) return;

    let cancelled = false;

    async function pollNewest() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const page = await fetchChannelMessages(channelId as number);
        if (!cancelled) {
          setMessages((prev) => {
            const next = prev.length === 0 ? [...page].reverse() : mergeNew(prev, page);
            oldestIdRef.current = next.length > 0 ? next[0].id : null;
            return next;
          });
          setHasMoreOlder(page.length === PAGE_SIZE);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        inFlight.current = false;
      }
    }

    pollNewest();
    const id = setInterval(pollNewest, POLL_INTERVAL_SECONDS * 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [channelId]);

  const loadOlder = useCallback(async () => {
    if (channelId === null || oldestIdRef.current === null || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const page = await fetchChannelMessages(channelId, oldestIdRef.current);
      setMessages((prev) => {
        const next = [...page].reverse().concat(prev);
        oldestIdRef.current = next.length > 0 ? next[0].id : null;
        return next;
      });
      setHasMoreOlder(page.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingOlder(false);
    }
  }, [channelId, loadingOlder]);

  return { messages, hasMoreOlder, loadingOlder, error, loadOlder };
}
