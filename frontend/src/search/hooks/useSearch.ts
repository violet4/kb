import { useEffect, useState } from 'react';
import { searchAll } from '../api';
import type { SearchHit } from '../types';

interface UseSearchResult {
  hits: SearchHit[];
  loading: boolean;
  error: string | null;
}

export function useSearch(query: string): UseSearchResult {
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setHits([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    searchAll(query)
      .then((result) => {
        if (!cancelled) setHits(result);
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
  }, [query]);

  return { hits, loading, error };
}
