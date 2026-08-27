import { useCallback, useEffect, useState } from 'react';
import { fetchEntity, fetchEntityGraph, fetchEntityJournal } from '../api';
import { rowToEntityDetail } from '../rowToEntityDetail';
import type { EntityDetail, EntityType, GraphNeighbor, JournalEntry } from '../types';

interface UseEntityResult {
  entity: EntityDetail | null;
  graph: GraphNeighbor[];
  journal: JournalEntry[];
  loading: boolean;
  error: string | null;
  applyFieldSave: (updated: EntityDetail) => void;
}

export function useEntity(type: EntityType, id: number): UseEntityResult {
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [graph, setGraph] = useState<GraphNeighbor[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchEntity(type, id), fetchEntityGraph(type, id), fetchEntityJournal(type, id)])
      .then(([entityResult, graphResult, journalResult]) => {
        if (cancelled) return;
        setEntity(rowToEntityDetail(entityResult));
        setGraph(graphResult);
        setJournal(journalResult);
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
  }, [type, id]);

  // A field save already returns the updated EntityDetail (no need to refetch it),
  // but it also creates a new Journal entry server-side -- refetch just that.
  const applyFieldSave = useCallback(
    (updated: EntityDetail) => {
      setEntity(updated);
      fetchEntityJournal(type, id).then(setJournal);
    },
    [type, id],
  );

  return { entity, graph, journal, loading, error, applyFieldSave };
}
