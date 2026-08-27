import type { ChannelMessage, ChannelSummary } from './types';

const API_BASE = '/api';

export async function fetchChannels(displayName: string): Promise<ChannelSummary[]> {
  const response = await fetch(`${API_BASE}/channels?display_name=${encodeURIComponent(displayName)}`);
  if (!response.ok) throw new Error(`Failed to load channels: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function fetchChannelMessages(channelId: number, beforeId?: number): Promise<ChannelMessage[]> {
  const params = new URLSearchParams();
  if (beforeId !== undefined) params.set('before_id', String(beforeId));
  const response = await fetch(`${API_BASE}/channels/${channelId}/messages?${params}`);
  if (!response.ok) throw new Error(`Failed to load messages: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function sendDirectMessage(
  displayName: string,
  agentSessionId: string,
  body: string,
): Promise<ChannelMessage> {
  const response = await fetch(`${API_BASE}/channels/dm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName, agent_session_id: agentSessionId, body }),
  });
  if (!response.ok) throw new Error(`Failed to send message: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function sendBroadcastMessage(displayName: string, body: string): Promise<ChannelMessage> {
  const response = await fetch(`${API_BASE}/channels/broadcast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName, body }),
  });
  if (!response.ok) throw new Error(`Failed to send broadcast: ${response.status} ${await response.text()}`);
  return response.json();
}
