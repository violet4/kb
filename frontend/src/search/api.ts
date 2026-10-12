import { checked } from '../shared/http';
import type { SearchHit, SearchInfo } from './types';

export async function searchAll(query: string): Promise<SearchHit[]> {
  const path = `/search-all?q=${encodeURIComponent(query)}`;
  return checked(await fetch(`/api${path}`), path);
}

export async function fetchSearchInfo(): Promise<SearchInfo> {
  return checked(await fetch('/api/search-all/info'), '/search-all/info');
}
