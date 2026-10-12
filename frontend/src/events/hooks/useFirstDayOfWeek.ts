import { useStoredState } from '../../shared/useStoredState';

// 0=Sunday .. 6=Saturday, matching Date.getDay()'s own numbering.
const DEFAULT_FIRST_DAY = 0;

const isWeekday = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 6;

export function useFirstDayOfWeek(): [number, (day: number) => void] {
  return useStoredState('kb-events-first-day-of-week', DEFAULT_FIRST_DAY, isWeekday);
}
