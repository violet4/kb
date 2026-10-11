import type { LogItem } from './types';

const API_BASE = '/api';

async function checked<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      detail = JSON.parse(text).detail ?? text;
    } catch {
      // non-JSON error body: show it as-is
    }
    throw new Error(`${path} -> ${response.status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
  }
  return response.json();
}

export async function fetchRecentLog(limit = 50): Promise<LogItem[]> {
  const path = `/log/recent?limit=${limit}`;
  return checked(await fetch(`${API_BASE}${path}`), path);
}

export async function createLogEntry(body: string, contextId: number): Promise<LogItem> {
  const response = await fetch(`${API_BASE}/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body, context_id: contextId }),
  });
  return checked(response, '/log');
}
