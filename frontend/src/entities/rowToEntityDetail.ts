import type { EntityDetail, EntityRow } from './types';

// The generic entity API returns a flat row (type/id/label + every column, un-nested).
// EntityView's renderers were built against an older {type, id, label, status,
// context_name, created_at, updated_at, fields: {...}} shape -- rather than rewrite
// every renderer for the flat shape, adapt at the one boundary that reads a fresh row.
export function rowToEntityDetail(row: EntityRow): EntityDetail {
  const { type, id, label, status, context_name, created_at, updated_at, ...rest } = row;
  return {
    type,
    id,
    label,
    status: (status as string | null) ?? null,
    context_name: (context_name as string | null) ?? null,
    created_at: created_at as string,
    updated_at: updated_at as string,
    fields: rest,
  };
}
