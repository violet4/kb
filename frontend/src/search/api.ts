import { checked } from '../shared/http';
import type { SearchHit, SearchInfo } from './types';

export async function searchAll(query: string, maxDist: number | null = null): Promise<SearchHit[]> {
  const path = `/search-all?q=${encodeURIComponent(query)}${maxDist === null ? '' : `&max_dist=${maxDist}`}`;
  return checked(await fetch(`/api${path}`), path);
}

export async function fetchSearchInfo(): Promise<SearchInfo> {
  return checked(await fetch('/api/search-all/info'), '/search-all/info');
}
