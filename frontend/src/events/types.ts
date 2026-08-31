// Mirrors api/events_router.py's EventOut Pydantic model.
export interface Event {
  id: number;
  title: string;
  starts_at: string;
  is_all_day: boolean;
  recurrence: string | null;
  notes: string | null;
  context_name: string | null;
  tag_name: string | null;
  next_occurrence: string | null;
}
