import type { ContextNode, ContextPage } from './types';

const API_BASE = '/api';

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`Request failed: ${path} -> ${response.status} ${await response.text()}`);
  return response.json();
}

export function fetchContextTree(): Promise<ContextNode[]> {
  return getJson('/contexts/tree');
}

export function fetchContextPage(id: number, includeDescendants: boolean): Promise<ContextPage> {
  return getJson(`/contexts/${id}?include_descendants=${includeDescendants}`);
}
