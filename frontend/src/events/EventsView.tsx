import { useState } from 'react';
import { tokens } from '../shared/tokens';
import EventsList from './components/EventsList';
import TodayHighlightSettings from './components/TodayHighlightSettings';
import ViewModeTabs from './components/ViewModeTabs';
import type { ViewMode } from './components/ViewModeTabs';
import { useEvents } from './hooks/useEvents';
import { useTodayHighlight } from './hooks/useTodayHighlight';
import MonthView from './MonthView';
import WeekView from './WeekView';

export default function EventsView() {
  const [mode, setMode] = useState<ViewMode>('list');
  const todayHighlight = useTodayHighlight();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0 }}>
      <EventsHeader mode={mode} onModeChange={setMode} todayHighlight={todayHighlight} />
      {mode === 'list' && <EventsListPane />}
      {mode === 'week' && <WeekView todayHighlightColor={todayHighlight.color} />}
      {mode === 'month' && <MonthView todayHighlightColor={todayHighlight.color} />}
    </div>
  );
}

function EventsHeader({
  mode,
  onModeChange,
  todayHighlight,
}: {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  todayHighlight: ReturnType<typeof useTodayHighlight>;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 8px 0' }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Events</h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <TodayHighlightSettings
          rgb={todayHighlight.rgb}
          alpha={todayHighlight.alpha}
          onChangeRgb={todayHighlight.setRgb}
          onChangeAlpha={todayHighlight.setAlpha}
        />
        <ViewModeTabs mode={mode} onChange={onModeChange} />
      </div>
    </div>
  );
}

function EventsListPane() {
  const [upcomingOnly, setUpcomingOnly] = useState(true);
  const { events, loading, error } = useEvents(upcomingOnly);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '0 8px 8px' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, alignSelf: 'flex-end' }}>
        <input type="checkbox" checked={upcomingOnly} onChange={(e) => setUpcomingOnly(e.target.checked)} />
        upcoming only
      </label>
      {loading && <p style={{ color: tokens.color.textMuted }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && <EventsList events={events} />}
    </div>
  );
}
