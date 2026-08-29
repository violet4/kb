import type { EntityType } from './types';

// Mirrors api/entities_router.py's _label fallback order (title, then name, then
// description, then body) -- the one place both BrowseView (which column to hide as
// redundant in the table) and EntityHeader (which column to edit when the label is
// clicked) agree on which column actually backs a given type's label.
const LABEL_COLUMN_OVERRIDES: Partial<Record<EntityType, string>> = {
  Daily: 'description',
  LogEntry: 'body',
};

export function labelColumnName(type: EntityType): string {
  return LABEL_COLUMN_OVERRIDES[type] ?? 'title';
}
