import { checked, sendJson } from '../shared/http';
import type { LogItem } from './types';

export async function fetchRecentLog(limit = 50): Promise<LogItem[]> {
  const path = `/log/recent?limit=${limit}`;
  return checked(await fetch(`/api${path}`), path);
}

export function createLogEntry(body: string, contextId: number): Promise<LogItem> {
  return sendJson('POST', '/log', { body, context_id: contextId });
}
