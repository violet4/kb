import { isPositiveNumber, useStoredState } from '../../shared/useStoredState';

export const DEFAULT_REFRESH_INTERVAL_SECONDS = 1;

export function useRefreshIntervalSetting(): [number, (value: number) => void] {
  return useStoredState('kb-agents-refresh-interval-seconds', DEFAULT_REFRESH_INTERVAL_SECONDS, isPositiveNumber);
}
