import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-agents-refresh-interval-ms';
export const DEFAULT_REFRESH_INTERVAL_MS = 1000;

export function useRefreshIntervalSetting(): [number, (value: number) => void] {
  const [intervalMs, setIntervalMsState] = useState(() => {
    const stored = Number(localStorage.getItem(STORAGE_KEY));
    return stored > 0 ? stored : DEFAULT_REFRESH_INTERVAL_MS;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(intervalMs));
  }, [intervalMs]);

  return [intervalMs, setIntervalMsState];
}
