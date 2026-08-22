import { tokens } from '../shared/tokens';
import BackgroundImagePicker from './components/BackgroundImagePicker';
import RefreshControl from './components/RefreshControl';
import UsageBar from './components/UsageBar';
import { useBackgroundImage } from './hooks/useBackgroundImage';
import { useUsage } from './hooks/useUsage';

const SESSION_PERIOD_MS = 5 * 60 * 60 * 1000;
const WEEK_PERIOD_MS = 7 * 24 * 60 * 60 * 1000;

// A bare filesystem path (no scheme) is loaded as file:// -- a URL is used as-is.
function resolveBackgroundUrl(backgroundImage: string): string | null {
  if (!backgroundImage) return null;
  return /^[a-z][a-z0-9+.-]*:/i.test(backgroundImage) ? backgroundImage : `file://${backgroundImage}`;
}

export default function UsageView() {
  const { usage, loading, error, lastUpdatedAt, nextRefreshAt, refresh } = useUsage();
  const { backgroundImage, setBackgroundImage } = useBackgroundImage();
  const backgroundUrl = resolveBackgroundUrl(backgroundImage);

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
          <RefreshControl lastUpdatedAt={lastUpdatedAt} nextRefreshAt={nextRefreshAt} onRefresh={refresh} />
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
          {loading && <p style={{ margin: 0, color: tokens.color.textMuted }}>Loading...</p>}
          {error && (
            <p style={{ margin: 0, color: tokens.color.danger }}>
              {error}
            </p>
          )}
          {usage && !loading && !error && (
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
      </div>
    </div>
  );
}
