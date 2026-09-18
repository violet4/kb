import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-events-first-day-of-week';

// 0=Sunday .. 6=Saturday, matching Date.getDay()'s own numbering.
const DEFAULT_FIRST_DAY = 0;

export function useFirstDayOfWeek(): [number, (day: number) => void] {
  const [firstDay, setFirstDay] = useState(() => readStored());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(firstDay));
  }, [firstDay]);

  return [firstDay, setFirstDay];
}

function readStored(): number {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === null) return DEFAULT_FIRST_DAY;
  const parsed = JSON.parse(raw);
  if (typeof parsed === 'number' && parsed >= 0 && parsed <= 6) return parsed;
  return DEFAULT_FIRST_DAY;
}
