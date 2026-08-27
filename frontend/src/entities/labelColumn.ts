import type { EntityType } from './types';

// Mirrors api/entities_router.py's _label fallback order (title, then name, then
// description) -- the one place both BrowseView (which column to hide as redundant
// in the table) and EntityHeader (which column to edit when the label is clicked)
// agree on which column actually backs a given type's label.
const TITLELESS_TYPES = new Set<EntityType>(['Daily']);

export function labelColumnName(type: EntityType): string {
  return TITLELESS_TYPES.has(type) ? 'description' : 'title';
}
