import { useState } from 'react';
import { tokens } from '../shared/tokens';
import EventFormModal from './components/EventFormModal';
import EventsList from './components/EventsList';
import TodayHighlightSettings from './components/TodayHighlightSettings';
import ViewModeTabs from './components/ViewModeTabs';
import type { ViewMode } from './components/ViewModeTabs';
import { useEventColors } from './hooks/useEventColors';
import { useEventFormModalState } from './hooks/useEventFormModalState';
import { useEvents } from './hooks/useEvents';
import { useFirstDayOfWeek } from './hooks/useFirstDayOfWeek';
import { useTodayHighlight } from './hooks/useTodayHighlight';
import { useViewModeKeyNav } from './hooks/useViewModeKeyNav';
import MonthView from './MonthView';
import WeekView from './WeekView';

export default function EventsView() {
  const [mode, setMode] = useState<ViewMode>('month');
  const todayHighlight = useTodayHighlight();
  const eventColors = useEventColors();
  const [firstDayOfWeek, setFirstDayOfWeek] = useFirstDayOfWeek();
  useViewModeKeyNav(setMode);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0 }}>
      <EventsHeader
        mode={mode}
        onModeChange={setMode}
        todayHighlight={todayHighlight}
        eventColors={eventColors}
        firstDayOfWeek={firstDayOfWeek}
        onChangeFirstDayOfWeek={setFirstDayOfWeek}
      />
      {mode === 'list' && <EventsListPane />}
      {mode === 'week' && (
        <WeekView
          todayHighlightColor={todayHighlight.color}
          recurringColor={eventColors.recurringColor}
          oneTimeColor={eventColors.oneTimeColor}
        />
      )}
      {mode === 'month' && (
        <MonthView
          todayHighlightColor={todayHighlight.color}
          recurringColor={eventColors.recurringColor}
          oneTimeColor={eventColors.oneTimeColor}
        />
      )}
    </div>
  );
}

function EventsHeader({
  mode,
  onModeChange,
  todayHighlight,
  eventColors,
  firstDayOfWeek,
  onChangeFirstDayOfWeek,
}: {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  todayHighlight: ReturnType<typeof useTodayHighlight>;
  eventColors: ReturnType<typeof useEventColors>;
  firstDayOfWeek: number;
  onChangeFirstDayOfWeek: (day: number) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '8px 8px 0' }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Events</h1>
      <TodayHighlightSettings
        rgb={todayHighlight.rgb}
        alpha={todayHighlight.alpha}
        onChangeRgb={todayHighlight.setRgb}
        onChangeAlpha={todayHighlight.setAlpha}
        recurringRgb={eventColors.recurringRgb}
        oneTimeRgb={eventColors.oneTimeRgb}
        onChangeRecurringRgb={eventColors.setRecurringRgb}
        onChangeOneTimeRgb={eventColors.setOneTimeRgb}
        firstDayOfWeek={firstDayOfWeek}
        onChangeFirstDayOfWeek={onChangeFirstDayOfWeek}
      />
      <ViewModeTabs mode={mode} onChange={onModeChange} />
    </div>
  );
}

function EventsListPane() {
  const [upcomingOnly, setUpcomingOnly] = useState(true);
  const { events, loading, error, refetch } = useEvents(upcomingOnly);
  const modal = useEventFormModalState();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '0 8px 8px' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, alignSelf: 'flex-start' }}>
        <input type="checkbox" checked={upcomingOnly} onChange={(e) => setUpcomingOnly(e.target.checked)} />
        upcoming only
      </label>
      {loading && <p style={{ color: tokens.color.textMuted }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && (
        <div style={{ userSelect: 'none' }}>
          <EventsList events={events} onEventDoubleClick={modal.openForEdit} />
        </div>
      )}
      <EventFormModal date={modal.date} existing={modal.existing} onClose={modal.close} onSaved={refetch} />
    </div>
  );
}
