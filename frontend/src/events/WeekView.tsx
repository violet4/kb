import { tokens } from '../shared/tokens';
import CalendarNav from './components/CalendarNav';
import EventFormModal from './components/EventFormModal';
import TimeGridDay from './components/TimeGridDay';
import { addDays, isSameDay, startOfWeek, weekDays } from './calendarMath';
import { useCalendarKeyNav } from './hooks/useCalendarKeyNav';
import { useCalendarNav } from './hooks/useCalendarNav';
import { useEventFormModalState } from './hooks/useEventFormModalState';
import { useEventsInRange } from './hooks/useEventsInRange';

const HOUR_HEIGHT = 48; // px per hour -- must match TimeGridDay's own HOUR_HEIGHT

export default function WeekView({ todayHighlightColor }: WeekViewProps) {
  const { anchor, goToPrev, goToNext, goToToday } = useCalendarNav(7);
  useCalendarKeyNav(goToPrev, goToNext, goToToday);
  const days = weekDays(anchor);
  const rangeStart = startOfWeek(anchor);
  const rangeEnd = addDays(rangeStart, 7);
  const { occurrences, loading, error, refetch } = useEventsInRange(rangeStart, rangeEnd);
  const modal = useEventFormModalState();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0, padding: '0 8px 8px' }}>
      <CalendarNav label={formatWeekLabel(days[0], days[6])} onPrev={goToPrev} onNext={goToNext} onToday={goToToday} />
      {loading && <p style={{ color: tokens.color.textMuted, margin: 0 }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger, margin: 0 }}>{error}</p>}
      {!loading && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, userSelect: 'none' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '48px repeat(7, 1fr)', flexShrink: 0 }}>
            <div />
            {days.map((date) => (
              <DayHeader key={date.toISOString()} date={date} />
            ))}
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '48px repeat(7, 1fr)' }}>
              <HourLabels />
              {days.map((date) => (
                <TimeGridDay
                  key={date.toISOString()}
                  date={date}
                  occurrences={occurrences}
                  todayHighlightColor={todayHighlightColor}
                  onDoubleClick={modal.openForNewEvent}
                  onEventDoubleClick={modal.openForEdit}
                />
              ))}
            </div>
          </div>
        </div>
      )}
      <EventFormModal date={modal.date} existing={modal.existing} onClose={modal.close} onSaved={refetch} />
    </div>
  );
}

interface WeekViewProps {
  todayHighlightColor: string;
}

function DayHeader({ date }: { date: Date }) {
  const today = isSameDay(date, new Date());
  return (
    <div style={{ textAlign: 'center', padding: '4px 0', fontSize: 12, color: today ? tokens.color.accent : tokens.color.textMuted }}>
      <div style={{ fontWeight: today ? 700 : 400 }}>{date.toLocaleDateString(undefined, { weekday: 'short' })}</div>
      <div>{date.getDate()}</div>
    </div>
  );
}

function HourLabels() {
  return (
    <div style={{ position: 'relative', height: 24 * HOUR_HEIGHT }}>
      {Array.from({ length: 24 }, (_, hour) => (
        <span
          key={hour}
          style={{
            position: 'absolute',
            top: hour * HOUR_HEIGHT - 6,
            right: 4,
            fontSize: 10,
            color: tokens.color.textMuted,
          }}
        >
          {formatHourLabel(hour)}
        </span>
      ))}
    </div>
  );
}

function formatHourLabel(hour: number): string {
  if (hour === 0) return '12a';
  if (hour === 12) return '12p';
  return hour < 12 ? `${hour}a` : `${hour - 12}p`;
}

function formatWeekLabel(start: Date, end: Date): string {
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  const yearOpts: Intl.DateTimeFormatOptions = { ...opts, year: 'numeric' };
  const sameYear = start.getFullYear() === end.getFullYear();
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, sameYear ? opts : yearOpts)}, ${end.getFullYear()}`;
}
