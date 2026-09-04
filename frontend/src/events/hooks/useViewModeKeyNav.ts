import { useEffect } from 'react';
import type { ViewMode } from '../components/ViewModeTabs';

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/** Binds l/w/m (list/week/month) to switch the Events page's view mode, page-wide --
 * a level above useCalendarKeyNav's own j/k/arrows/t, which only apply once inside
 * Week/Month. Ignored while focus is inside an editable element (the event form
 * modal's fields), same guard as useCalendarKeyNav, so typing "m" into a title or
 * notes field doesn't also switch views underneath it. */
export function useViewModeKeyNav(onChange: (mode: ViewMode) => void): void {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      const target = e.target as HTMLElement | null;
      if (target && (EDITABLE_TAGS.has(target.tagName) || target.isContentEditable)) return;

      if (e.key === 'l') onChange('list');
      else if (e.key === 'w') onChange('week');
      else if (e.key === 'm') onChange('month');
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onChange]);
}
