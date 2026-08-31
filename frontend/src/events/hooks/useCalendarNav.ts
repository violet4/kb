import { useCallback, useState } from 'react';

interface UseCalendarNavResult {
  anchor: Date;
  goToPrev: () => void;
  goToNext: () => void;
  goToToday: () => void;
}

/** Tracks the currently-viewed date for a calendar grid, stepping by `stepDays` (7 for
 * a week grid) or, when stepDays is 'month', by calendar month -- shared nav logic
 * behind both WeekView and MonthView so the prev/next/today behavior has one owner. */
export function useCalendarNav(step: number | 'month'): UseCalendarNavResult {
  const [anchor, setAnchor] = useState(new Date());

  const goToPrev = useCallback(() => {
    setAnchor((d) => shift(d, step, -1));
  }, [step]);

  const goToNext = useCallback(() => {
    setAnchor((d) => shift(d, step, 1));
  }, [step]);

  const goToToday = useCallback(() => {
    setAnchor(new Date());
  }, []);

  return { anchor, goToPrev, goToNext, goToToday };
}

function shift(date: Date, step: number | 'month', direction: 1 | -1): Date {
  if (step === 'month') {
    return new Date(date.getFullYear(), date.getMonth() + direction, 1);
  }
  const d = new Date(date);
  d.setDate(d.getDate() + step * direction);
  return d;
}
