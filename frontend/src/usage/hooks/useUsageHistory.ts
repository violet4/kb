import { useEffect, useState } from 'react';
import { fetchUsageHistory } from '../api';
import type { UsageSample } from '../types';

interface UseUsageHistoryResult {
  samples: UsageSample[];
  loading: boolean;
  error: string | null;
}

// Polls at the same 1-minute cadence as useUsage -- recording is throttled to at most
// 1 sample/minute server-side (see kb_cli/usage.py's _CACHE_MAX_AGE), so polling faster
// would just re-fetch the same rows.
const POLL_INTERVAL_MS = 60_000;

export function useUsageHistory(hours: number): UseUsageHistoryResult {
  const [samples, setSamples] = useState<UsageSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await fetchUsageHistory(hours);
        if (!cancelled) {
          setSamples(result);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [hours]);

  return { samples, loading, error };
}
