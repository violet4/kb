import { useEffect, useState } from 'react';
import { searchAll } from '../api';
import type { SearchHit } from '../types';

interface UseSearchResult {
  hits: SearchHit[];
  resultsFor: string | null; // the query `hits` answer (lags `query` while a new one runs)
  loading: boolean;
  error: string | null;
  refresh: () => void; // re-run the same query, e.g. after a hit was moved
}

// maxDist: the semantic distance cutoff; null uses the backend's default.
export function useSearch(query: string, maxDist: number | null = null): UseSearchResult {
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [resultsFor, setResultsFor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    if (!query.trim()) {
      setHits([]);
      setResultsFor(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    searchAll(query, maxDist)
      .then((result) => {
        if (!cancelled) {
          setHits(result);
          setResultsFor(query);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, maxDist, generation]);

  return { hits, resultsFor, loading, error, refresh: () => setGeneration((g) => g + 1) };
}
