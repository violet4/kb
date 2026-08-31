import { useState } from 'react';
import { tokens } from '../shared/tokens';
import CalendarNav from './components/CalendarNav';
import DayCell from './components/DayCell';
import NewEventModal from './components/NewEventModal';
import { addDays, isSameMonth, monthGridDays, monthGridStart } from './calendarMath';
import { useCalendarNav } from './hooks/useCalendarNav';
import { useEventsInRange } from './hooks/useEventsInRange';

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface MonthViewProps {
  todayHighlightColor: string;
}

export default function MonthView({ todayHighlightColor }: MonthViewProps) {
  const { anchor, goToPrev, goToNext, goToToday } = useCalendarNav('month');
  const days = monthGridDays(anchor);
  const rangeStart = monthGridStart(anchor);
  const rangeEnd = addDays(rangeStart, 42);
  const { occurrences, loading, error, refetch } = useEventsInRange(rangeStart, rangeEnd);
  const [newEventDate, setNewEventDate] = useState<Date | null>(null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0, padding: '0 8px 8px' }}>
      <CalendarNav label={formatMonthLabel(anchor)} onPrev={goToPrev} onNext={goToNext} onToday={goToToday} />
      {loading && <p style={{ color: tokens.color.textMuted, margin: 0 }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger, margin: 0 }}>{error}</p>}
      {!loading && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1, minHeight: 0 }}>
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
                onDoubleClick={setNewEventDate}
              />
            ))}
          </div>
        </div>
      )}
      <NewEventModal date={newEventDate} onClose={() => setNewEventDate(null)} onCreated={refetch} />
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
