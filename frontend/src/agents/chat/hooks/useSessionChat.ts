import { useEffect, useState } from 'react';
import { fetchSessionChat } from '../api';
import { addressMessage, type AddressedBlock } from '../blockAddress';
import type { ChatMessage } from '../types';

export interface TranscriptEntry {
  message: ChatMessage;
  blocks: AddressedBlock[];
}

interface UseSessionChatResult {
  entries: TranscriptEntry[];
  loading: boolean;
  error: string | null;
}

// Loads a session transcript, then polls for messages appended after it, every
// intervalSeconds. Each poll sends the previous response's byte offset, so the server parses
// only new lines, and new entries are appended to the existing array without touching the
// ones already there -- rows already on screen keep their props and do not re-render, which
// is what keeps a text selection in them intact while a live session writes. Polls run one
// at a time (the next is scheduled after the previous settles), so two responses for the
// same offset can never both append. A past session's transcript no longer grows, so its
// polls return nothing.
export function useSessionChat(sessionId: string, intervalSeconds: number): UseSessionChatResult {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let offset = 0;
    let count = 0;
    setEntries([]);
    setLoading(true);
    setError(null);

    async function poll() {
      try {
        const page = await fetchSessionChat(sessionId, offset);
        if (cancelled) return;
        offset = page.next_offset;
        if (page.messages.length > 0) {
          const start = count;
          count += page.messages.length;
          const added = page.messages.map((message, i) => ({ message, blocks: addressMessage(message, start + i) }));
          setEntries((prev) => [...prev, ...added]);
        }
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
      setLoading(false);
      timer = setTimeout(poll, intervalSeconds * 1000);
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId, intervalSeconds]);

  return { entries, loading, error };
}
