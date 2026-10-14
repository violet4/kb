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
  // Why the page must not send a prompt / press Esc now, or null when it may (kb_cli/sessions.py).
  prompt_blocker: string | null;
  interrupt_blocker: string | null;
}

// Mirrors api/sessions_router.py's HistorySessionOut Pydantic model.
export interface HistorySession {
  id: string;
  project: string;
  title: string;
  timestamp: string;
  message_count: number;
}

// Mirrors api/sessions_router.py's HistoryProjectOut Pydantic model.
export interface HistoryProject {
  project: string;
  session_count: number;
}
