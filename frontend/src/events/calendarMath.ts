// Pure date-grid math shared by WeekView/MonthView -- kept logic-only (no JSX, no
// React) so the grid-shape computation is testable/reasoned-about independent of
// rendering, per kb instructions #42 (data-and-logic).

/** Local midnight for the given date, dropping any time-of-day component. */
export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** The Monday on or before `date` (ISO week start), at local midnight. */
export function startOfWeek(date: Date): Date {
  const d = startOfDay(date);
  const dayNum = d.getDay() || 7; // Sunday (0) -> 7, so Mon=1..Sun=7
  d.setDate(d.getDate() - (dayNum - 1));
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** The 7 local-midnight dates of the Mon-Sun week containing `date`. */
export function weekDays(date: Date): Date[] {
  const start = startOfWeek(date);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

/** The Monday starting the first full week shown for `date`'s month -- may fall in
 * the previous month, so the grid's first row still shows a complete Mon-Sun week. */
export function monthGridStart(date: Date): Date {
  const firstOfMonth = new Date(date.getFullYear(), date.getMonth(), 1);
  return startOfWeek(firstOfMonth);
}

/** 6 full Mon-Sun weeks (42 days) starting at monthGridStart -- a fixed 6-row grid so
 * the page layout doesn't reflow height between 4/5/6-week months. */
export function monthGridDays(date: Date): Date[] {
  const start = monthGridStart(date);
  return Array.from({ length: 42 }, (_, i) => addDays(start, i));
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function isSameMonth(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

/** Whether an occurrence instant belongs on `gridDay` (a local-midnight grid cell
 * date). A timed occurrence is bucketed by its local wall-clock date (isSameDay) --
 * the same instant can land on different grid days for viewers in different zones,
 * which is correct, matching what a clock on the wall in that viewer's zone would say.
 * An all-day occurrence is bucketed by its UTC calendar date instead: it's stored as
 * UTC midnight on the intended date (see models.py's Event docstring) specifically so
 * every viewer sees the same date regardless of their own zone -- comparing it via
 * local date components would reintroduce exactly the day-off bug that storage
 * convention exists to prevent (a UTC midnight instant reads back as the previous
 * local day for any viewer west of UTC). */
export function occurrenceFallsOnDay(occursAt: Date, gridDay: Date, isAllDay: boolean): boolean {
  if (isAllDay) {
    return (
      occursAt.getUTCFullYear() === gridDay.getFullYear() &&
      occursAt.getUTCMonth() === gridDay.getMonth() &&
      occursAt.getUTCDate() === gridDay.getDate()
    );
  }
  return isSameDay(occursAt, gridDay);
}
