import { useEffect, useState } from 'react';
import { fetchHistoryProjects, fetchHistorySessions } from '../api';
import type { HistoryProject, HistorySession } from '../types';

interface UseAgentHistoryProjectsResult {
  projects: HistoryProject[];
  isLoading: boolean;
  error: string | null;
}

// Past sessions don't change while the picker is open (unlike live sessions), so this is a
// plain fetch-once-per-selection, not usePolling -- there is nothing to keep fresh.
// isLoading distinguishes "still fetching" from "fetched, and there's nothing" -- both start
// as an empty projects/sessions array, so callers need it to tell "No sessions found" apart
// from a load still in flight.
export function useAgentHistoryProjects(): UseAgentHistoryProjectsResult {
  const [projects, setProjects] = useState<HistoryProject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    fetchHistoryProjects()
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { projects, isLoading, error };
}

interface UseAgentHistorySessionsResult {
  sessions: HistorySession[];
  isLoading: boolean;
  error: string | null;
}

// project === null means "all projects"; see AgentHistoryView.
export function useAgentHistorySessions(project: string | null): UseAgentHistorySessionsResult {
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    fetchHistorySessions(project)
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [project]);

  return { sessions, isLoading, error };
}
