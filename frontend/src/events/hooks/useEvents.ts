import { useCallback, useEffect, useState } from 'react';
import { fetchEvents } from '../api';
import type { Event } from '../types';

interface UseEventsResult {
  events: Event[];
  loading: boolean;
  error: string | null;
}

export function useEvents(upcomingOnly: boolean): UseEventsResult {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEvents(await fetchEvents(upcomingOnly));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [upcomingOnly]);

  useEffect(() => {
    load();
  }, [load]);

  return { events, loading, error };
}
