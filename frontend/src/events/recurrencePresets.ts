// Maps a small set of common recurrence patterns to RFC 5545 RRULE strings, anchored
// to a given date -- the "friendly UX" layer in front of the raw RRULE textbox. Kept
// as pure functions (no JSX) per kb instructions #42 (data-and-logic): the mapping
// logic is reasoned about and testable independent of the dropdown that calls it.

export type RecurrencePreset = 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'every-n-days' | 'custom';

const WEEKDAY_CODES = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'];

export const PRESET_LABELS: { value: RecurrencePreset; label: string }[] = [
  { value: 'none', label: 'Does not repeat' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'every-n-days', label: 'Every N days' },
  { value: 'custom', label: 'Custom (RRULE)' },
];

/** Builds the RRULE string for a preset anchored to `date` -- e.g. 'weekly' on a
 * Wednesday becomes FREQ=WEEKLY;BYDAY=WE. `everyN` only applies to 'every-n-days'. */
export function rruleForPreset(preset: RecurrencePreset, date: Date, everyN: number): string {
  switch (preset) {
    case 'none':
    case 'custom':
      return '';
    case 'daily':
      return 'FREQ=DAILY';
    case 'weekly':
      return `FREQ=WEEKLY;BYDAY=${WEEKDAY_CODES[(date.getDay() + 6) % 7]}`;
    case 'monthly':
      return `FREQ=MONTHLY;BYMONTHDAY=${date.getDate()}`;
    case 'yearly':
      return `FREQ=YEARLY;BYMONTH=${date.getMonth() + 1};BYMONTHDAY=${date.getDate()}`;
    case 'every-n-days':
      return `FREQ=DAILY;INTERVAL=${Math.max(1, everyN)}`;
  }
}

/** Human-readable description of an RRULE string, anchored to `date` for the day-name
 * used in the weekly case -- shown next to the raw textbox so a hand-typed or preset-
 * generated rule is legible without decoding the RRULE grammar by eye. Best-effort:
 * covers exactly the shapes rruleForPreset generates plus falls back to the raw string
 * for anything else (a custom rule with BYSETPOS, COUNT, etc.). */
export function describeRrule(rrule: string, date: Date): string {
  if (!rrule.trim()) return 'Does not repeat';
  const parts = Object.fromEntries(rrule.split(';').map((p) => p.split('=') as [string, string]));
  const weekdayName = date.toLocaleDateString(undefined, { weekday: 'long' });

  if (parts.FREQ === 'DAILY' && !parts.INTERVAL) return 'Repeats every day';
  if (parts.FREQ === 'DAILY' && parts.INTERVAL) return `Repeats every ${parts.INTERVAL} days`;
  if (parts.FREQ === 'WEEKLY' && parts.BYDAY && !parts.BYDAY.includes(',')) return `Repeats weekly on ${weekdayName}`;
  if (parts.FREQ === 'MONTHLY' && parts.BYMONTHDAY) return `Repeats monthly on day ${parts.BYMONTHDAY}`;
  if (parts.FREQ === 'YEARLY' && parts.BYMONTH && parts.BYMONTHDAY) {
    const monthName = new Date(2000, Number(parts.BYMONTH) - 1, 1).toLocaleDateString(undefined, { month: 'long' });
    return `Repeats yearly on ${monthName} ${parts.BYMONTHDAY}`;
  }
  return `Custom: ${rrule}`;
}

/** Which preset (if any) `rrule` matches, for initializing the dropdown when editing
 * an existing Event -- 'custom' if it doesn't match a known preset shape exactly. */
export function presetForRrule(rrule: string): RecurrencePreset {
  if (!rrule.trim()) return 'none';
  if (rrule === 'FREQ=DAILY') return 'daily';
  if (/^FREQ=WEEKLY;BYDAY=[A-Z]{2}$/.test(rrule)) return 'weekly';
  if (/^FREQ=MONTHLY;BYMONTHDAY=\d{1,2}$/.test(rrule)) return 'monthly';
  if (/^FREQ=YEARLY;BYMONTH=\d{1,2};BYMONTHDAY=\d{1,2}$/.test(rrule)) return 'yearly';
  if (/^FREQ=DAILY;INTERVAL=\d+$/.test(rrule)) return 'every-n-days';
  return 'custom';
}
