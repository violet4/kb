import type { Usage } from './types';

// /api (not http://127.0.0.1:25690) so requests go through Vite's dev
// proxy (see vite.config.ts) and stay same-origin.
const API_BASE = '/api';

export async function fetchUsage(): Promise<Usage> {
  const response = await fetch(`${API_BASE}/usage`);
  if (!response.ok) throw new Error(`Failed to load usage: ${response.status} ${await response.text()}`);
  return response.json();
}
