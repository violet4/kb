import { tokens } from '../shared/tokens';
import CalendarNav from './components/CalendarNav';
import DayCell from './components/DayCell';
import EventFormModal from './components/EventFormModal';
import { addDays, isSameMonth, monthGridDays, monthGridStart } from './calendarMath';
import { useCalendarKeyNav } from './hooks/useCalendarKeyNav';
import { useCalendarNav } from './hooks/useCalendarNav';
import { useEventFormModalState } from './hooks/useEventFormModalState';
import { useEventsInRange } from './hooks/useEventsInRange';

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface MonthViewProps {
  todayHighlightColor: string;
  recurringColor: string;
  oneTimeColor: string;
}

export default function MonthView({ todayHighlightColor, recurringColor, oneTimeColor }: MonthViewProps) {
  const { anchor, goToPrev, goToNext, goToToday } = useCalendarNav('month');
  useCalendarKeyNav(goToPrev, goToNext, goToToday);
  const days = monthGridDays(anchor);
  const rangeStart = monthGridStart(anchor);
  const rangeEnd = addDays(rangeStart, 42);
  const { occurrences, loading, error, refetch } = useEventsInRange(rangeStart, rangeEnd);
  const modal = useEventFormModalState();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0, padding: '0 8px 8px' }}>
      <CalendarNav label={formatMonthLabel(anchor)} onPrev={goToPrev} onNext={goToNext} onToday={goToToday} centerLabel />
      {loading && <p style={{ color: tokens.color.textMuted, margin: 0 }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger, margin: 0 }}>{error}</p>}
      {!loading && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1, minHeight: 0, userSelect: 'none' }}>
          <WeekdayHeaderRow />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gridTemplateRows: 'repeat(6, 1fr)',
              gap: 1,
              flex: 1,
              minHeight: 0,
            }}
          >
            {days.map((date) => (
              <DayCell
                key={date.toISOString()}
                date={date}
                occurrences={occurrences}
                dimmed={!isSameMonth(date, anchor)}
                todayHighlightColor={todayHighlightColor}
                recurringColor={recurringColor}
                oneTimeColor={oneTimeColor}
                onDoubleClick={(d) => modal.openForNewEvent(withDefaultTime(d))}
                onEventDoubleClick={modal.openForEdit}
              />
            ))}
          </div>
        </div>
      )}
      <EventFormModal date={modal.date} existing={modal.existing} onClose={modal.close} onSaved={refetch} />
    </div>
  );
}

function WeekdayHeaderRow() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1 }}>
      {WEEKDAY_LABELS.map((label) => (
        <span key={label} style={{ fontSize: 12, color: tokens.color.textMuted, textAlign: 'center', padding: 2 }}>
          {label}
        </span>
      ))}
    </div>
  );
}

function formatMonthLabel(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

/** Month view's day cells carry no time-of-day (local midnight) -- unlike WeekView's
 * time grid, where a double-click position maps to a real hour, there's nothing here
 * to derive a time from, so this fills in the same 9am default useEventForm used to
 * hardcode before the time field started reading it off the clicked date. */
function withDefaultTime(date: Date): Date {
  const withTime = new Date(date);
  withTime.setHours(9, 0, 0, 0);
  return withTime;
}
