// Mirrors api/log_router.py's response models.

export interface ContextRef {
  id: number;
  name: string;
}

export interface LogItem {
  id: number;
  body: string;
  domain: string | null;
  context: ContextRef;
  occurred_at_utc: string | null;
  created_at_utc: string | null;
}
