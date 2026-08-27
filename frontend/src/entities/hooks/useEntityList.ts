import { useCallback, useEffect, useState } from 'react';
import { fetchEntityList } from '../api';
import type { EntityRow, EntityType } from '../types';

interface UseEntityListResult {
  entities: EntityRow[];
  loading: boolean;
  error: string | null;
  applyFieldSave: (updated: EntityRow) => void;
}

export function useEntityList(type: EntityType, filters: Record<string, string>): UseEntityListResult {
  const [entities, setEntities] = useState<EntityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Stringify so the effect dependency doesn't re-fire on every render just because
  // the caller passed a fresh object literal with the same contents.
  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchEntityList(type, filters)
      .then((result) => {
        if (!cancelled) setEntities(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, filtersKey]);

  // A row's field is edited in place (EnumFieldSelect) -- patch just that row from
  // the PATCH response rather than refetching the whole list.
  const applyFieldSave = useCallback((updated: EntityRow) => {
    setEntities((prev) => prev.map((e) => (e.type === updated.type && e.id === updated.id ? updated : e)));
  }, []);

  return { entities, loading, error, applyFieldSave };
}
