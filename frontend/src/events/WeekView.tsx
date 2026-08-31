import { tokens } from '../shared/tokens';
import CalendarNav from './components/CalendarNav';
import DayCell from './components/DayCell';
import { addDays, startOfWeek, weekDays } from './calendarMath';
import { useCalendarNav } from './hooks/useCalendarNav';
import { useEventsInRange } from './hooks/useEventsInRange';

interface WeekViewProps {
  todayHighlightColor: string;
}

export default function WeekView({ todayHighlightColor }: WeekViewProps) {
  const { anchor, goToPrev, goToNext, goToToday } = useCalendarNav(7);
  const days = weekDays(anchor);
  const rangeStart = startOfWeek(anchor);
  const rangeEnd = addDays(rangeStart, 7);
  const { occurrences, loading, error } = useEventsInRange(rangeStart, rangeEnd);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0, padding: '0 8px 8px' }}>
      <CalendarNav label={formatWeekLabel(days[0], days[6])} onPrev={goToPrev} onNext={goToNext} onToday={goToToday} />
      {loading && <p style={{ color: tokens.color.textMuted, margin: 0 }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger, margin: 0 }}>{error}</p>}
      {!loading && !error && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1, flex: 1, minHeight: 0 }}>
          {days.map((date) => (
            <DayCell
              key={date.toISOString()}
              date={date}
              occurrences={occurrences}
              todayHighlightColor={todayHighlightColor}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function formatWeekLabel(start: Date, end: Date): string {
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  const yearOpts: Intl.DateTimeFormatOptions = { ...opts, year: 'numeric' };
  const sameYear = start.getFullYear() === end.getFullYear();
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, sameYear ? opts : yearOpts)}, ${end.getFullYear()}`;
}
