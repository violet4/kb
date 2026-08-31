import { useCallback, useEffect, useState } from 'react';
import { fetchEventsInRange } from '../api';
import type { EventOccurrence } from '../api';

interface UseEventsInRangeResult {
  occurrences: EventOccurrence[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/** start/end should be stable across renders (e.g. memoized) -- a new Date instance
 * every render would refetch on every render regardless of whether the range moved. */
export function useEventsInRange(start: Date, end: Date): UseEventsInRangeResult {
  const [occurrences, setOccurrences] = useState<EventOccurrence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const startMs = start.getTime();
  const endMs = end.getTime();

  // Depend on the primitive timestamps, not the Date objects themselves -- a fresh
  // Date instance every render (even for the same instant) would otherwise refetch
  // on every render regardless of whether the actual range moved.
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOccurrences(await fetchEventsInRange(new Date(startMs), new Date(endMs)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [startMs, endMs]);

  useEffect(() => {
    load();
  }, [load]);

  return { occurrences, loading, error, refetch: load };
}
