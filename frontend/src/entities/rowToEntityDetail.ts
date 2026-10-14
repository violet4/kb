import type { Placement } from '../contexts/types';
import type { EntityDetail, EntityRow } from './types';

// The generic entity API returns a flat row (type/id/label + every column, un-nested).
// EntityView's renderers were built against an older {type, id, label, status,
// placement, created_at, updated_at, fields: {...}} shape -- rather than rewrite
// every renderer for the flat shape, adapt at the one boundary that reads a fresh row.
export function rowToEntityDetail(row: EntityRow): EntityDetail {
  const { type, id, label, status, context, created_at, updated_at, deleted_at, ...rest } = row;
  return {
    type,
    id,
    label,
    status: (status as string | null) ?? null,
    placement: (context as Placement | undefined) ?? null, // the "context" column, kind "placement"
    created_at: created_at as string,
    updated_at: updated_at as string,
    deleted_at: (deleted_at as string | null | undefined) ?? null,
    // status is kept in fields too (not just the top-level header copy above) so
    // type-specific renderers (e.g. TodoView's "Status" Field) can read+edit it --
    // see kb Todo #82 debugging session, status silently vanished from the body
    // because it only existed at EntityDetail.status, never in fields.
    fields: { ...rest, status },
  };
}
