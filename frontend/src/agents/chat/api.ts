import type { ChatMessage } from './types';

const API_BASE = '/api';

export async function fetchSessionChat(sessionId: string): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/chat`);
  if (!response.ok) throw new Error(`Failed to load chat: ${response.status} ${await response.text()}`);
  return response.json();
}
