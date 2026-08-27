import { useEffect, useRef, useState } from 'react';
import { fetchChannels } from '../api';
import type { ChannelSummary } from '../types';

interface UseChannelListResult {
  channels: ChannelSummary[];
  error: string | null;
}

// Same fixed-schedule polling shape as ../../agents/hooks/useAgentSessions -- one poll
// mechanism pattern reused rather than reinvented per feature.
export function useChannelList(displayName: string, intervalSeconds: number): UseChannelListResult {
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const result = await fetchChannels(displayName);
        if (!cancelled) {
          setChannels(result);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        inFlight.current = false;
      }
    }

    poll();
    const id = setInterval(poll, intervalSeconds * 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [displayName, intervalSeconds]);

  return { channels, error };
}
