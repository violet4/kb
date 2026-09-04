import { tokens } from '../../shared/tokens';
import type { EventOccurrence } from '../api';
import { isSameDay, occurrenceFallsOnDay } from '../calendarMath';
import type { Event } from '../types';

const HOUR_HEIGHT = 48; // px per hour, midnight (top) to midnight (bottom) = 24 * HOUR_HEIGHT tall
const MINUTES_PER_DAY = 24 * 60;

interface TimeGridDayProps {
  date: Date;
  occurrences: EventOccurrence[];
  todayHighlightColor: string;
  onDoubleClick?: (date: Date) => void;
  onEventDoubleClick?: (event: Event) => void;
}

/** One day's column in the week view's time grid: a fixed-height midnight-to-midnight
 * track (see HOUR_HEIGHT) with each timed occurrence placed by simple top-offset =
 * minutes-since-midnight, no width/overlap packing -- concurrent events just stack in
 * DOM order at the same left edge and visually overlap. This is a deliberate
 * complexity tradeoff (minimize logic for the overlap case, per the request that
 * introduced this view) rather than an oversight; a day with heavily overlapping
 * events is rare enough in this app's own usage that full lane-packing isn't worth
 * the added code. */
export default function TimeGridDay({
  date,
  occurrences,
  todayHighlightColor,
  onDoubleClick,
  onEventDoubleClick,
}: TimeGridDayProps) {
  const dayOccurrences = occurrences.filter((occ) =>
    occurrenceFallsOnDay(new Date(occ.occurs_at), date, occ.event.is_all_day),
  );
  const allDay = dayOccurrences.filter((occ) => occ.event.is_all_day);
  const timed = dayOccurrences.filter((occ) => !occ.event.is_all_day);
  const today = isSameDay(date, new Date());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      {allDay.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '2px 4px' }}>
          {allDay.map((occ) => (
            <EventBlock key={occ.event.id} event={occ.event} onDoubleClick={onEventDoubleClick} />
          ))}
        </div>
      )}
      <div
        onDoubleClick={
          onDoubleClick
            ? (e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                onDoubleClick(dateAtOffset(date, e.clientY - rect.top));
              }
            : undefined
        }
        style={{
          position: 'relative',
          height: (MINUTES_PER_DAY / 60) * HOUR_HEIGHT,
          borderLeft: `1px solid ${tokens.color.border}`,
          borderRight: `1px solid ${tokens.color.border}`,
          background: today ? todayCellBackground(todayHighlightColor) : tokens.color.surface,
          cursor: onDoubleClick ? 'pointer' : undefined,
        }}
      >
        <HourLines />
        {timed.map((occ) => (
          <TimedEventBlock
            key={`${occ.event.id}-${occ.occurs_at}`}
            occurrence={occ}
            onDoubleClick={onEventDoubleClick}
          />
        ))}
      </div>
    </div>
  );
}

function HourLines() {
  return (
    <>
      {Array.from({ length: 24 }, (_, hour) => (
        <div
          key={hour}
          style={{
            position: 'absolute',
            top: hour * HOUR_HEIGHT,
            left: 0,
            right: 0,
            borderTop: `1px solid ${tokens.color.border}`,
          }}
        />
      ))}
    </>
  );
}

function TimedEventBlock({
  occurrence,
  onDoubleClick,
}: {
  occurrence: EventOccurrence;
  onDoubleClick?: (event: Event) => void;
}) {
  const occursAt = new Date(occurrence.occurs_at);
  const minutesFromMidnight = occursAt.getHours() * 60 + occursAt.getMinutes();
  return (
    <div
      style={{
        position: 'absolute',
        top: (minutesFromMidnight / 60) * HOUR_HEIGHT,
        height: HOUR_HEIGHT,
        left: 2,
        right: 2,
      }}
    >
      <EventBlock event={occurrence.event} onDoubleClick={onDoubleClick} showTime occursAt={occursAt} fillHeight />
    </div>
  );
}

function EventBlock({
  event,
  onDoubleClick,
  showTime,
  occursAt,
  fillHeight,
}: {
  event: Event;
  onDoubleClick?: (event: Event) => void;
  showTime?: boolean;
  occursAt?: Date;
  fillHeight?: boolean;
}) {
  return (
    <div
      title={event.title}
      onDoubleClick={
        onDoubleClick
          ? (e) => {
              e.stopPropagation();
              onDoubleClick(event);
            }
          : undefined
      }
      style={{
        boxSizing: 'border-box',
        height: fillHeight ? '100%' : undefined,
        fontSize: 11,
        padding: '2px 4px',
        borderRadius: 3,
        borderLeft: `3px solid ${event.recurrence ? tokens.color.accent : tokens.color.textMuted}`,
        background: tokens.color.background,
        color: tokens.color.text,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        cursor: onDoubleClick ? 'pointer' : undefined,
      }}
    >
      {showTime && occursAt && (
        <span style={{ color: tokens.color.textMuted }}>
          {occursAt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}{' '}
        </span>
      )}
      {event.title}
    </div>
  );
}

// Mirrors DayCell's todayCellBackground -- see its comment for why this is a two-stop
// gradient rather than a plain background-color.
function todayCellBackground(highlightColor: string): string {
  return `linear-gradient(${highlightColor}, ${highlightColor}), ${tokens.color.surface}`;
}

const SNAP_MINUTES = 15;

/** `offsetY` is the double-click's y position within the day column, in pixels from
 * the midnight (top) edge -- converts that back to a time-of-day on `date`, snapped to
 * the nearest 15 minutes so a slightly-off click still lands on a clean time rather
 * than an arbitrary pixel-derived minute. */
function dateAtOffset(date: Date, offsetY: number): Date {
  const rawMinutes = (offsetY / HOUR_HEIGHT) * 60;
  const clamped = Math.max(0, Math.min(MINUTES_PER_DAY - SNAP_MINUTES, rawMinutes));
  const snapped = Math.round(clamped / SNAP_MINUTES) * SNAP_MINUTES;
  const result = new Date(date);
  result.setHours(0, snapped, 0, 0);
  return result;
}
