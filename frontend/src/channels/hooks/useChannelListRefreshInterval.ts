import { isPositiveNumber, useStoredState } from '../../shared/useStoredState';

export const DEFAULT_CHANNEL_REFRESH_INTERVAL_SECONDS = 5;

export function useChannelListRefreshInterval(): [number, (value: number) => void] {
  return useStoredState(
    'kb-channels-refresh-interval-seconds',
    DEFAULT_CHANNEL_REFRESH_INTERVAL_SECONDS,
    isPositiveNumber,
  );
}
