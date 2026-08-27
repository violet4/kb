import { useEffect, useState } from 'react';
import { fetchColumns } from '../api';
import type { ColumnSchema, EntityType } from '../types';

// Fetched once per page (not per row/field) and keyed by column name, so every
// consumer on the page -- the table, the filter bar, N editable fields -- shares one
// /entities/{type}/columns request instead of each fetching its own copy.
export function useColumns(type: EntityType): Record<string, ColumnSchema> {
  const [columns, setColumns] = useState<Record<string, ColumnSchema>>({});

  useEffect(() => {
    let cancelled = false;
    fetchColumns(type).then((result) => {
      if (cancelled) return;
      setColumns(Object.fromEntries(result.map((c) => [c.name, c])));
    });
    return () => {
      cancelled = true;
    };
  }, [type]);

  return columns;
}
