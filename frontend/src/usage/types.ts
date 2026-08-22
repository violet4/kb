// Mirrors api/usage_router.py's UsageOut Pydantic model.
export interface Usage {
  session_pct: number;
  session_resets: string;
  session_resets_at: string;
  week_pct: number;
  week_resets: string;
  week_resets_at: string;
}
