import type { SearchHit } from './types';

const API_BASE = '/api';

export async function searchAll(query: string): Promise<SearchHit[]> {
  const response = await fetch(`${API_BASE}/search-all?q=${encodeURIComponent(query)}`);
  if (!response.ok) throw new Error(`Search failed: ${response.status} ${await response.text()}`);
  return response.json();
}
