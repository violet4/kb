import { useCallback } from 'react';
import { usePolling } from '../../shared/usePolling';
import { fetchAgentSessions } from '../api';
import type { AgentSession } from '../types';

interface UseAgentSessionsResult {
  sessions: AgentSession[];
  error: string | null;
}

// Polls at intervalSeconds on a fixed schedule (not a "wait intervalSeconds after the
// previous response") so the settings-panel refresh rate reads as the true cadence a viewer
// sees, matching RefreshControl's countdown model in ../../usage. See usePolling for the
// shared, generation-scoped poll mechanism this builds on.
export function useAgentSessions(intervalSeconds: number): UseAgentSessionsResult {
  const fetcher = useCallback(() => fetchAgentSessions(), []);
  const { data, error } = usePolling(fetcher, intervalSeconds);
  return { sessions: data ?? [], error };
}
