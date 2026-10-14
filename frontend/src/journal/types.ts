import type { JournalEntry } from '../entities/types';
import type { RecordHit } from '../search/types';

// Mirrors api/journal_router.py's TimelineEntry and TimelinePage.
export interface TimelineEntry extends JournalEntry {
  entity_type: string;
  entity_id: number;
  record: RecordHit | null; // null once purged, or for a type with no table (SiNode)
}

export interface TimelinePage {
  entries: TimelineEntry[];
  next_before: number | null; // the `before` for the next, older page; null at the start of history
}
