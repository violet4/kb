import type { AgentSession, HistoryProject, HistorySession } from './types';

const API_BASE = '/api';

export async function fetchAgentSessions(): Promise<AgentSession[]> {
  const response = await fetch(`${API_BASE}/sessions`);
  if (!response.ok) throw new Error(`Failed to load sessions: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function fetchHistoryProjects(): Promise<HistoryProject[]> {
  const response = await fetch(`${API_BASE}/sessions/history/projects`);
  if (!response.ok) throw new Error(`Failed to load projects: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function fetchHistorySessions(project: string | null): Promise<HistorySession[]> {
  const url = project
    ? `${API_BASE}/sessions/history?project=${encodeURIComponent(project)}`
    : `${API_BASE}/sessions/history`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load sessions: ${response.status} ${await response.text()}`);
  return response.json();
}
