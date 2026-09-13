import { tokens } from '../../shared/tokens';
import type { EventOccurrence } from '../api';
import { isSameDay, occurrenceFallsOnDay } from '../calendarMath';
import type { Event } from '../types';
import OccurrenceChip from './OccurrenceChip';

interface DayCellProps {
  date: Date;
  occurrences: EventOccurrence[];
  dimmed?: boolean;
  todayHighlightColor: string;
  recurringColor: string;
  oneTimeColor: string;
  onDoubleClick?: (date: Date) => void;
  onEventDoubleClick?: (event: Event) => void;
}

export default function DayCell({
  date,
  occurrences,
  dimmed,
  todayHighlightColor,
  recurringColor,
  oneTimeColor,
  onDoubleClick,
  onEventDoubleClick,
}: DayCellProps) {
  const dayOccurrences = occurrences.filter((occ) =>
    occurrenceFallsOnDay(new Date(occ.occurs_at), date, occ.event.is_all_day),
  );
  const today = isSameDay(date, new Date());

  return (
    <div
      onDoubleClick={onDoubleClick ? () => onDoubleClick(date) : undefined}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: 6,
        minHeight: 0,
        overflow: 'hidden',
        border: `1px solid ${today ? todayHighlightColor : tokens.color.border}`,
        background: today ? todayCellBackground(todayHighlightColor) : tokens.color.surface,
        opacity: dimmed ? 0.5 : 1,
        cursor: onDoubleClick ? 'pointer' : undefined,
      }}
    >
      <DayCellHeader date={date} today={today} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, overflow: 'auto', minHeight: 0 }}>
        {dayOccurrences.map((occ) => (
          <OccurrenceChip
            key={`${occ.event.id}-${occ.occurs_at}`}
            occurrence={occ}
            onDoubleClick={onEventDoubleClick}
            recurringColor={recurringColor}
            oneTimeColor={oneTimeColor}
          />
        ))}
      </div>
    </div>
  );
}

// The whole cell shape gets a gentle wash for today, not just the border/date-number
// text -- a low-alpha, bright color (rgba, see useTodayHighlight) layered over the
// normal surface color via a two-stop gradient rather than replacing it outright, so
// the cell still reads as "surface" underneath the tint instead of showing whatever
// sits behind the element (a plain rgba background-color would blend against that,
// not against tokens.color.surface).
function todayCellBackground(highlightColor: string): string {
  return `linear-gradient(${highlightColor}, ${highlightColor}), ${tokens.color.surface}`;
}

function DayCellHeader({ date, today }: { date: Date; today: boolean }) {
  return (
    <span
      style={{
        fontSize: 12,
        fontWeight: today ? 700 : 400,
        color: today ? tokens.color.accent : tokens.color.textMuted,
      }}
    >
      {date.getDate()}
    </span>
  );
}
