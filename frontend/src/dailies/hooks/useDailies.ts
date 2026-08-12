import { useCallback, useEffect, useState } from 'react';
import { catchUpDaily, completeDaily, fetchDailies } from '../api';
import type { Daily } from '../types';

interface UseDailiesResult {
  dailies: Daily[];
  loading: boolean;
  error: string | null;
  complete: (id: number) => Promise<void>;
  catchUp: (id: number) => Promise<void>;
}

export function useDailies(dueOnly: boolean): UseDailiesResult {
  const [dailies, setDailies] = useState<Daily[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // showSpinner is false for a post-action refresh (complete/catch-up) so the
  // list doesn't unmount behind a "Loading..." placeholder on every click --
  // only the initial load and a dueOnly toggle should show that.
  const load = useCallback(
    async (showSpinner: boolean) => {
      if (showSpinner) setLoading(true);
      setError(null);
      try {
        setDailies(await fetchDailies(dueOnly));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (showSpinner) setLoading(false);
      }
    },
    [dueOnly],
  );

  useEffect(() => {
    load(true);
  }, [load]);

  // Poll for content changes (e.g. a daily rolling over at midnight) without
  // showing the loading spinner on every tick.
  useEffect(() => {
    const interval = setInterval(() => load(false), 60_000);
    return () => clearInterval(interval);
  }, [load]);

  const withReload = useCallback(
    (action: (id: number) => Promise<Daily>) => async (id: number) => {
      await action(id);
      await load(false);
    },
    [load],
  );

  return {
    dailies,
    loading,
    error,
    complete: withReload(completeDaily),
    catchUp: withReload(catchUpDaily),
  };
}
