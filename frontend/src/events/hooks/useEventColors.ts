import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-events-colors';

const DEFAULT_RECURRING = '124, 58, 237'; // matches useTodayHighlight's royal-purple accent default
const DEFAULT_ONE_TIME = '148, 163, 184'; // muted gray, matching tokens.color.textMuted's old hardcoded look

interface StoredColors {
  recurring: string;
  oneTime: string;
}

interface UseEventColorsResult {
  recurringRgb: string;
  oneTimeRgb: string;
  recurringColor: string;
  oneTimeColor: string;
  setRecurringRgb: (rgb: string) => void;
  setOneTimeRgb: (rgb: string) => void;
}

/** The left-border color distinguishing a recurring Event from a one-time one, shared
 * by every calendar view (MonthView's OccurrenceChip, WeekView's TimeGridDay) --
 * persisted the same way useTodayHighlight persists its own color, so this is a
 * sibling hook rather than folded into that one (today-highlight and event-kind color
 * are unrelated settings that happen to both be per-viewer color preferences). */
export function useEventColors(): UseEventColorsResult {
  const [{ recurring, oneTime }, setState] = useState<StoredColors>(() => readStored());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ recurring, oneTime }));
  }, [recurring, oneTime]);

  return {
    recurringRgb: recurring,
    oneTimeRgb: oneTime,
    recurringColor: `rgb(${recurring})`,
    oneTimeColor: `rgb(${oneTime})`,
    setRecurringRgb: (value) => setState((s) => ({ ...s, recurring: value })),
    setOneTimeRgb: (value) => setState((s) => ({ ...s, oneTime: value })),
  };
}

function readStored(): StoredColors {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return { recurring: DEFAULT_RECURRING, oneTime: DEFAULT_ONE_TIME };
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed.recurring === 'string' && typeof parsed.oneTime === 'string') return parsed;
  } catch {
    // fall through to default
  }
  return { recurring: DEFAULT_RECURRING, oneTime: DEFAULT_ONE_TIME };
}
