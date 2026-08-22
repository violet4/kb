import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchUsage } from '../api';
import type { Usage } from '../types';

const POLL_INTERVAL_MS = 60_000;

interface UseUsageResult {
  usage: Usage | null;
  loading: boolean;
  error: string | null;
  lastUpdatedAt: number | null;
  nextRefreshAt: number | null;
  requestStartedAt: number | null;
  refresh: () => void;
}

export function useUsage(): UseUsageResult {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [nextRefreshAt, setNextRefreshAt] = useState<number | null>(null);
  const [requestStartedAt, setRequestStartedAt] = useState<number | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (showSpinner: boolean) => {
    if (showSpinner) setLoading(true);
    setError(null);
    setRequestStartedAt(Date.now());
    try {
      setUsage(await fetchUsage());
      setLastUpdatedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (showSpinner) setLoading(false);
      setRequestStartedAt(null);
    }
  }, []);

  // schedule owns the recurring timer so a manual refresh can restart the
  // countdown from zero instead of leaving a stale interval running alongside it.
  const schedule = useCallback(
    (showSpinner: boolean) => {
      if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
      load(showSpinner);
      setNextRefreshAt(Date.now() + POLL_INTERVAL_MS);
      timeoutRef.current = setTimeout(() => schedule(false), POLL_INTERVAL_MS);
    },
    [load],
  );

  useEffect(() => {
    schedule(true);
    return () => {
      if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
    };
    // schedule intentionally omitted -- it's stable across the load it closes over,
    // and including it would re-arm the timer (and refetch) on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = useCallback(() => schedule(false), [schedule]);

  return { usage, loading, error, lastUpdatedAt, nextRefreshAt, requestStartedAt, refresh };
}
