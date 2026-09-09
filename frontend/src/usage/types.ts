// Mirrors api/usage_router.py's UsageOut Pydantic model. raw_text is set instead of the bar
// fields when claude -p /usage's output doesn't match the parseable session/week bar format
// (e.g. the no-usage-yet "behaviors contributing to your limits" summary).
export interface Usage {
  session_pct: number | null;
  session_resets: string | null;
  session_resets_at: string | null;
  week_pct: number | null;
  week_resets: string | null;
  week_resets_at: string | null;
  raw_text: string | null;
}

// Mirrors api/usage_router.py's UsageSampleOut Pydantic model -- one recorded history point.
export interface UsageSample {
  sampled_at: string;
  session_pct: number;
  session_resets_at: string;
  week_pct: number;
  week_resets_at: string;
}
