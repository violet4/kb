import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchChannels } from '../api';
import type { ChannelSummary } from '../types';

interface UseChannelListResult {
  channels: ChannelSummary[];
  error: string | null;
  refresh: () => void;
}

// Same fixed-schedule polling shape as ../../agents/hooks/useAgentSessions -- one poll
// mechanism pattern reused rather than reinvented per feature. refresh() lets a caller force
// an immediate re-fetch (e.g. right after sending a DM's first message, so the newly-created
// channel_id shows up without waiting up to intervalSeconds for the next scheduled poll).
export function useChannelList(displayName: string, intervalSeconds: number): UseChannelListResult {
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  // Bumped whenever displayName changes, so a response for a stale displayName arriving
  // late (after the user already changed it again) is discarded rather than clobbering
  // newer state -- setInterval/refresh() calls made after a displayName change all read the
  // current value via this ref, not a value closed over at effect-setup time.
  const requestGenerationRef = useRef(0);

  const poll = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    const generation = requestGenerationRef.current;
    try {
      const result = await fetchChannels(displayName);
      if (generation === requestGenerationRef.current) {
        setChannels(result);
        setError(null);
      }
    } catch (e) {
      if (generation === requestGenerationRef.current) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      inFlight.current = false;
    }
  }, [displayName]);

  useEffect(() => {
    requestGenerationRef.current += 1;
    poll();
    const id = setInterval(poll, intervalSeconds * 1000);
    return () => clearInterval(id);
  }, [poll, intervalSeconds]);

  return { channels, error, refresh: poll };
}
