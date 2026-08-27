import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-channels-refresh-interval-seconds';
export const DEFAULT_CHANNEL_REFRESH_INTERVAL_SECONDS = 5;

export function useChannelListRefreshInterval(): [number, (value: number) => void] {
  const [intervalSeconds, setIntervalSecondsState] = useState(() => {
    const stored = Number(localStorage.getItem(STORAGE_KEY));
    return stored > 0 ? stored : DEFAULT_CHANNEL_REFRESH_INTERVAL_SECONDS;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(intervalSeconds));
  }, [intervalSeconds]);

  return [intervalSeconds, setIntervalSecondsState];
}
