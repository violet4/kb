// Mirrors api/channels_router.py's ChannelSummaryOut/ChannelMessageOut Pydantic models.
export interface ChannelSummary {
  channel_id: number | null; // null until the first message is ever sent into this DM slot
  kind: 'dm' | 'named';
  name: string | null; // set for kind === 'named' (e.g. "broadcast")
  agent_session_id: string | null;
  agent_title: string;
  agent_cwd: string;
  last_message_at: string | null;
}

export interface ChannelMessage {
  id: number;
  from_session: string;
  from_title: string;
  body: string;
  created_at: string;
}
