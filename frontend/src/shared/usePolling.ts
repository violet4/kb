import { useCallback, useEffect, useRef, useState } from 'react';

interface UsePollingResult<T> {
  data: T | null;
  error: string | null;
  refresh: () => void;
}

// The one fixed-schedule poll mechanism every "keep this list fresh" hook in the app should
// build on (useAgentSessions, useChannelList, useChannelMessages) -- see kb-engineering's
// single-ownership rule: three hand-rolled copies of this same shape each had, or came close
// to having, the same StrictMode race (confirmed live 2026-08-28, kb frontend session): a
// mount->cleanup->remount effect cycle left an in-flight request from the original mount
// either blocking the remount's own poll (a bare `inFlight` boolean shared across both
// effect runs) or landing late and overwriting state that had already moved on. Generation-
// scoped tracking (bump a counter once per effect run, tag every request/response with the
// generation active when it started) fixes both failure modes at once: a new generation's
// poll is never blocked by an old one's still-pending request, and a stale generation's late
// response is always discarded rather than applied.
//
// fetcher must be stable across calls that should count as "the same poll," i.e. wrapped in
// useCallback by the caller with the real dependencies (matching how every existing caller
// already had to memoize its own fetch function for the interval closure) -- passing a fresh
// function identity every render would restart the poll schedule on every render.
export function usePolling<T>(fetcher: () => Promise<T>, intervalSeconds: number): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inFlightGenerationRef = useRef<number | null>(null);
  const requestGenerationRef = useRef(0);

  const poll = useCallback(async () => {
    const generation = requestGenerationRef.current;
    if (inFlightGenerationRef.current === generation) return;
    inFlightGenerationRef.current = generation;
    try {
      const result = await fetcher();
      if (generation === requestGenerationRef.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (generation === requestGenerationRef.current) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (inFlightGenerationRef.current === generation) inFlightGenerationRef.current = null;
    }
  }, [fetcher]);

  useEffect(() => {
    requestGenerationRef.current += 1;
    poll();
    const id = setInterval(poll, intervalSeconds * 1000);
    return () => clearInterval(id);
  }, [poll, intervalSeconds]);

  return { data, error, refresh: poll };
}
