// Mirrors api/contexts_router.py's response models.

export interface ContextRef {
  id: number;
  name: string;
}

export interface Counts {
  todos: number;
  goals: number;
  notes: number;
  wishlist: number;
}

export interface ContextNode {
  id: number;
  name: string;
  parent_id: number | null;
  tags: string[];
  counts: Counts; // items filed directly on this node, not its descendants
}

export interface GoalItem {
  id: number;
  title: string;
  status: string;
  context: ContextRef | null;
  via_tag: string | null;
}

export interface TodoItem {
  id: number;
  title: string;
  status: string;
  kind: string;
  effort: string | null;
  severity: string | null;
  urgent: boolean;
  defer_until_utc: string | null;
  goal: { id: number; title: string } | null;
  context: ContextRef | null;
  via_tag: string | null;
  updated_at_utc: string | null;
}

export interface NoteItem {
  id: number;
  title: string;
  collection: string;
  tags: string | null;
  context: ContextRef;
  updated_at_utc: string | null;
}

export interface WishlistItem {
  id: number;
  title: string;
  price_min: number | null;
  price_max: number | null;
  priority: number | null;
  pinned: boolean;
  context: ContextRef;
}

export interface ContextPage {
  context: ContextRef;
  description: string | null;
  tags: string[];
  ancestors: ContextRef[];
  children: ContextRef[];
  include_descendants: boolean;
  goals: GoalItem[];
  todos: TodoItem[];
  notes: NoteItem[];
  wishlist: WishlistItem[];
}
