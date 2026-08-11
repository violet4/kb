// Mirrors api/dailies_router.py's DailyOut Pydantic model.
export interface Daily {
  id: number;
  description: string;
  domain: string;
  tier: 'critical' | 'optional';
  recurrence: string;
  next_due_date: string;
  location: string | null;
  remind_days_before: number;
  is_active: boolean;
  notes: string | null;
  context_name: string | null;
  tag_name: string | null;
  is_due_now: boolean;
  is_overdue: boolean;
}
