import type { ColumnSchema, EntityRow, EntityType, GraphNeighbor, JournalEntry } from './types';

const API_BASE = '/api';

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`Request failed: ${path} -> ${response.status} ${await response.text()}`);
  return response.json();
}

export function fetchEntityTypes(): Promise<EntityType[]> {
  return getJson('/entities/types');
}

// Every real column this type has -- the frontend never hand-lists which fields
// exist per type; it derives display columns, filters, and edit controls from this.
export function fetchColumns(type: EntityType): Promise<ColumnSchema[]> {
  return getJson(`/entities/${type}/columns`);
}

// filters is any column name -> value (enum/text/bool/number, per that column's
// kind) -- forwarded straight through as query params, matching every real column
// this type has with no per-column parameter to add as new columns appear.
export function fetchEntityList(type: EntityType, filters: Record<string, string>): Promise<EntityRow[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return getJson(`/entities/${type}${qs ? `?${qs}` : ''}`);
}

export function fetchEntity(type: EntityType, id: number): Promise<EntityRow> {
  return getJson(`/entities/${type}/${id}`);
}

export function fetchEntityGraph(type: EntityType, id: number): Promise<GraphNeighbor[]> {
  return getJson(`/entities/${type}/${id}/graph`);
}

export function fetchEntityJournal(type: EntityType, id: number): Promise<JournalEntry[]> {
  return getJson(`/entities/${type}/${id}/journal`);
}

// isNull=true clears the column to NULL server-side and ignores `value` -- see
// api/entities_router.py's FieldUpdateIn.
export async function updateEntityField(
  type: EntityType,
  id: number,
  field: string,
  value: string,
  isNull = false,
): Promise<EntityRow> {
  const response = await fetch(`${API_BASE}/entities/${type}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ field, value, is_null: isNull }),
  });
  if (!response.ok) throw new Error(`Failed to update ${type}:${id}.${field} -> ${response.status} ${await response.text()}`);
  return response.json();
}
