import { useState } from 'react';
import { tokens } from '../shared/tokens';
import BackgroundImagePicker from './components/BackgroundImagePicker';
import PendingIndicator from './components/PendingIndicator';
import RefreshControl from './components/RefreshControl';
import UsageBar from './components/UsageBar';
import UsageHistoryChart from './components/UsageHistoryChart';
import { useBackgroundImage } from './hooks/useBackgroundImage';
import { useUsage } from './hooks/useUsage';
import { useUsageHistory } from './hooks/useUsageHistory';

const SESSION_PERIOD_MS = 5 * 60 * 60 * 1000;
const WEEK_PERIOD_MS = 7 * 24 * 60 * 60 * 1000;
const SESSION_PERIOD_HOURS = 5;
const WEEK_PERIOD_HOURS = 7 * 24;
const SHOW_CHART_STORAGE_KEY = 'kb-usage-show-chart';

function loadShowChart(): boolean {
  try {
    return localStorage.getItem(SHOW_CHART_STORAGE_KEY) !== 'false';
  } catch {
    return true;
  }
}

interface ChartModeToggleProps {
  cumulative: boolean;
  onChange: (cumulative: boolean) => void;
}

function ChartModeToggle({ cumulative, onChange }: ChartModeToggleProps) {
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {(['cumulative', 'per-slot'] as const).map((mode) => (
        <button
          key={mode}
          onClick={() => onChange(mode === 'cumulative')}
          style={{
            fontSize: 12,
            padding: '4px 10px',
            borderRadius: 6,
            border: `1px solid ${tokens.color.border}`,
            background: (mode === 'cumulative') === cumulative ? tokens.color.accent : 'transparent',
            color: (mode === 'cumulative') === cumulative ? tokens.color.background : tokens.color.textMuted,
            cursor: 'pointer',
          }}
        >
          {mode === 'cumulative' ? 'Cumulative' : 'Per slot'}
        </button>
      ))}
    </div>
  );
}

// A bare filesystem path (no scheme) is loaded as file:// -- a URL is used as-is.
function resolveBackgroundUrl(backgroundImage: string): string | null {
  if (!backgroundImage) return null;
  return /^[a-z][a-z0-9+.-]*:/i.test(backgroundImage) ? backgroundImage : `file://${backgroundImage}`;
}

export default function UsageView() {
  const { usage, loading, error, lastUpdatedAt, nextRefreshAt, requestStartedAt, refresh } = useUsage();
  const { backgroundImage, setBackgroundImage } = useBackgroundImage();
  const backgroundUrl = resolveBackgroundUrl(backgroundImage);
  const { samples: sessionHistorySamples } = useUsageHistory(SESSION_PERIOD_HOURS);
  const { samples: weekHistorySamples } = useUsageHistory(WEEK_PERIOD_HOURS);
  const [sessionCumulative, setSessionCumulative] = useState(true);
  const [weekCumulative, setWeekCumulative] = useState(true);
  const [showChart, setShowChart] = useState(loadShowChart);

  const toggleShowChart = () => {
    setShowChart((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SHOW_CHART_STORAGE_KEY, String(next));
      } catch {
        // localStorage unavailable (private browsing, blocked site data) -- the toggle still
        // works for this page load, it just won't persist across reloads.
      }
      return next;
    });
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundImage: backgroundUrl ? `url("${backgroundUrl}")` : undefined,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div style={{ maxWidth: 640, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <h1 style={{ margin: 0, fontSize: 20 }}>Usage</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RefreshControl lastUpdatedAt={lastUpdatedAt} nextRefreshAt={nextRefreshAt} onRefresh={refresh} />
            <button
              onClick={toggleShowChart}
              style={{
                fontSize: 12,
                padding: '4px 10px',
                borderRadius: 6,
                border: `1px solid ${tokens.color.border}`,
                background: 'transparent',
                color: tokens.color.textMuted,
                cursor: 'pointer',
              }}
            >
              {showChart ? 'Hide chart' : 'Show chart'}
            </button>
          </div>
        </div>
        <BackgroundImagePicker value={backgroundImage} onChange={setBackgroundImage} />
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            padding: 16,
            background: tokens.color.surface,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 8,
          }}
        >
          {requestStartedAt !== null && <PendingIndicator requestStartedAt={requestStartedAt} />}
          {error && (
            <p style={{ margin: 0, color: tokens.color.danger }}>
              {error}
            </p>
          )}
          {usage && !loading && !error && usage.raw_text !== null && (
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                fontFamily: 'inherit',
                fontSize: 14,
                color: tokens.color.text,
              }}
            >
              {usage.raw_text}
            </pre>
          )}
          {usage &&
            !loading &&
            !error &&
            usage.raw_text === null &&
            usage.session_pct !== null &&
            usage.session_resets_at !== null &&
            usage.week_pct !== null &&
            usage.week_resets_at !== null && (
              <>
                <UsageBar
                  label="Current session"
                  pct={usage.session_pct}
                  resetsAt={usage.session_resets_at}
                  periodMs={SESSION_PERIOD_MS}
                />
                <UsageBar
                  label="Current week (all models)"
                  pct={usage.week_pct}
                  resetsAt={usage.week_resets_at}
                  periodMs={WEEK_PERIOD_MS}
                />
              </>
            )}
        </div>
        {showChart && (
          <>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                padding: 16,
                background: tokens.color.surface,
                border: `1px solid ${tokens.color.border}`,
                borderRadius: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 style={{ margin: 0, fontSize: 15 }}>Session usage · last {SESSION_PERIOD_HOURS}h</h2>
                <ChartModeToggle cumulative={sessionCumulative} onChange={setSessionCumulative} />
              </div>
              <UsageHistoryChart
                samples={sessionHistorySamples}
                hours={SESSION_PERIOD_HOURS}
                cumulative={sessionCumulative}
                metric="session"
                bucketMinutes={1}
              />
            </div>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                padding: 16,
                background: tokens.color.surface,
                border: `1px solid ${tokens.color.border}`,
                borderRadius: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 style={{ margin: 0, fontSize: 15 }}>Week usage (all models) · last 7d</h2>
                <ChartModeToggle cumulative={weekCumulative} onChange={setWeekCumulative} />
              </div>
              <UsageHistoryChart
                samples={weekHistorySamples}
                hours={WEEK_PERIOD_HOURS}
                cumulative={weekCumulative}
                metric="week"
                bucketMinutes={60}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
