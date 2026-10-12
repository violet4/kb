import { useEffect, useState } from 'react';
import { fetchSearchInfo } from '../api';
import type { SearchInfo } from '../types';

// The backend's search parameters (models, default limit and cutoff), fetched once per page
// load and shared by every caller.
let cached: Promise<SearchInfo> | null = null;

export function useSearchInfo(): SearchInfo | null {
  const [info, setInfo] = useState<SearchInfo | null>(null);
  useEffect(() => {
    cached ??= fetchSearchInfo();
    cached.then(setInfo).catch(() => {
      cached = null; // retry on the next mount
    });
  }, []);
  return info;
}
