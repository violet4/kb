// Drilldown navigation is browser history itself (pushed via <Link>/navigate), not a
// separate parallel stack -- back/forward already behave like the ~img navigation stack,
// and a Link renders a real <a> so ctrl/middle-click open-in-new-tab work with zero
// special handling. entityPath is the one place the URL shape for an entity is decided.
import type { EntityType } from './types';

export function entityPath(type: EntityType, id: number): string {
  return `/entities/${type}/${id}`;
}
