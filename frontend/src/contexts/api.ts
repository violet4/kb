import { checked, sendJson } from '../shared/http';
import type { ContextNode, ContextPage, ContextRef, Placement, PlacementChoice, SessionRefs } from './types';

async function getJson<T>(path: string): Promise<T> {
  return checked(await fetch(`/api${path}`), path);
}

export function fetchContextTree(): Promise<ContextNode[]> {
  return getJson('/contexts/tree');
}

export function fetchContextPage(id: number, includeDescendants: boolean): Promise<ContextPage> {
  return getJson(`/contexts/${id}?include_descendants=${includeDescendants}`);
}

export function createContext(name: string, parentId: number | null): Promise<ContextNode> {
  return sendJson('POST', '/contexts', { name, parent_id: parentId });
}

export function moveContext(id: number, parentId: number | null): Promise<ContextNode> {
  return sendJson('PUT', `/contexts/${id}/parent`, { parent_id: parentId });
}

export function fetchTags(): Promise<ContextRef[]> {
  return getJson('/contexts/tags');
}

export function fetchInbox(): Promise<ContextRef> {
  return getJson('/contexts/inbox');
}

// Works for any record type with a context, not only the Browse types (search hits include Items etc.).
export function setPlacement(type: string, id: number, choice: PlacementChoice): Promise<Placement> {
  return sendJson('PUT', `/entities/${type}/${id}/placement`, choice);
}

export type QuickCreateType = 'Goal' | 'Todo' | 'Note' | 'Wishlist';

// A new record with only a title, filed in the given context; the entity page sets the rest.
export function quickCreate(type: QuickCreateType, title: string, contextId: number): Promise<{ id: number }> {
  return sendJson('POST', `/entities/${type}`, { title, context_id: contextId });
}

export function fetchSessionRefs(harnessId: string): Promise<SessionRefs> {
  return getJson(`/sessions/${encodeURIComponent(harnessId)}/refs`);
}
