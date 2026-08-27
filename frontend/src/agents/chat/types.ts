// Mirrors api/sessions_router.py's ChatMessageOut/ChatBlockOut Pydantic models.
export interface ChatBlock {
  kind: 'text' | 'tool_use' | 'tool_result' | 'unknown';
  text: string | null;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  is_error: boolean;
  // Every scalar field kb_cli/sessions.py's _flatten_tags found on this block and its
  // parent message -- deliberately open-ended so a legend/filter panel can be built from
  // whatever keys/values actually occur, with no fixed field list on this side either.
  tags: Record<string, string>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  timestamp: string;
  blocks: ChatBlock[];
}
