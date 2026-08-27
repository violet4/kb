import { useEffect, useRef, useState } from 'react';
import { fetchAgentSessions } from '../api';
import type { AgentSession } from '../types';

interface UseAgentSessionsResult {
  sessions: AgentSession[];
  error: string | null;
}

// Polls at intervalMs on a fixed schedule (not a "wait intervalMs after the previous
// response") so the settings-panel refresh rate reads as the true cadence a viewer sees,
// matching RefreshControl's countdown model in ../../usage.
export function useAgentSessions(intervalMs: number): UseAgentSessionsResult {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const result = await fetchAgentSessions();
        if (!cancelled) {
          setSessions(result);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        inFlight.current = false;
      }
    }

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return { sessions, error };
}
