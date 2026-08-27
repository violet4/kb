import type { AgentSession } from './types';

const API_BASE = '/api';

export async function fetchAgentSessions(): Promise<AgentSession[]> {
  const response = await fetch(`${API_BASE}/sessions`);
  if (!response.ok) throw new Error(`Failed to load sessions: ${response.status} ${await response.text()}`);
  return response.json();
}
