import { useEffect } from 'react';

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/** Binds ArrowLeft/ArrowRight and j/k (nvim-style prev/next), plus "t" (jump to
 * today), to step the calendar grid -- shared by WeekView/MonthView. Ignored while
 * focus is inside an editable element (the new-event modal's fields) so typing "k" or
 * "t" into a title doesn't also page the calendar underneath it. */
export function useCalendarKeyNav(onPrev: () => void, onNext: () => void, onToday: () => void): void {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      const target = e.target as HTMLElement | null;
      if (target && (EDITABLE_TAGS.has(target.tagName) || target.isContentEditable)) return;

      if (e.key === 'ArrowLeft' || e.key === 'k') onPrev();
      else if (e.key === 'ArrowRight' || e.key === 'j') onNext();
      else if (e.key === 't') onToday();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onPrev, onNext, onToday]);
}
