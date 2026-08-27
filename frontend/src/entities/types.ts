// Mirrors api/entities_router.py's Pydantic models.
export type EntityType = 'Todo' | 'Goal' | 'Note' | 'Idea' | 'Wishlist';

// A raw row from GET /entities/{type} or /entities/{type}/{id} -- type/id/label
// are always present, everything else is whatever columns that type actually has
// (see ColumnSchema), flat on the object rather than a fixed set of fields.
export interface EntityRow {
  type: EntityType;
  id: number;
  label: string;
  [column: string]: unknown;
}

// Legacy adapted shape EntityView's renderers were built against -- see
// rowToEntityDetail.ts, the one place a fresh EntityRow is reshaped into this.
export interface EntityDetail {
  type: EntityType;
  id: number;
  label: string;
  status: string | null;
  context_name: string | null;
  created_at: string;
  updated_at: string;
  fields: Record<string, unknown>;
}

export interface GraphNeighbor {
  link_id: number;
  relation: string;
  direction: 'outgoing' | 'incoming';
  note: string | null;
  other_type: string;
  other_id: number;
  other_label: string;
  other_exists: boolean;
}

// Mirrors api/entities_router.py's ColumnSchema -- one entry per real column a type
// has (plus resolved relationship references), covering display (shown), editing
// (editable, choices), and filtering (kind) all from the same introspected shape.
export interface ColumnSchema {
  name: string;
  kind: 'text' | 'enum' | 'bool' | 'number' | 'date' | 'reference';
  choices: string[] | null;
  shown: boolean;
  editable: boolean;
  nullable: boolean;
}

export interface JournalEntry {
  id: number;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  note: string | null;
  created_at: string;
}
