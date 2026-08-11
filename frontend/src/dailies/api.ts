import type { Daily } from './types';

// /api (not http://127.0.0.1:25690) so requests go through Vite's dev
// proxy (see vite.config.ts) and stay same-origin.
const API_BASE = '/api';

export async function fetchDailies(dueOnly: boolean): Promise<Daily[]> {
  const response = await fetch(`${API_BASE}/dailies?due_only=${dueOnly}`);
  if (!response.ok) throw new Error(`Failed to load dailies: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function completeDaily(id: number): Promise<Daily> {
  const response = await fetch(`${API_BASE}/dailies/${id}/complete`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to complete daily ${id}: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function catchUpDaily(id: number): Promise<Daily> {
  const response = await fetch(`${API_BASE}/dailies/${id}/catch-up`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to catch up daily ${id}: ${response.status} ${await response.text()}`);
  return response.json();
}
