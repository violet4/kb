import type { ChatMessage } from './types';

const API_BASE = '/api';

// Mirrors api/sessions_router.py's ChatPageOut Pydantic model.
export interface ChatPage {
  messages: ChatMessage[];
  next_offset: number;
}

// offset is the previous page's next_offset (0 for the whole transcript), so polling a live
// session transfers and parses only what was appended since the last poll.
export async function fetchSessionChat(sessionId: string, offset: number): Promise<ChatPage> {
  const response = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/chat?offset=${offset}`);
  if (!response.ok) throw new Error(`Failed to load chat: ${response.status} ${await response.text()}`);
  return response.json();
}
