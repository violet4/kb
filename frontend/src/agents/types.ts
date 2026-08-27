// Mirrors api/sessions_router.py's SessionOut Pydantic model.
export interface AgentSession {
  id: string;
  is_self: boolean;
  status: string;
  listening: string;
  age_seconds: number;
  last_message_seconds: number | null;
  cwd: string;
  title: string;
}
