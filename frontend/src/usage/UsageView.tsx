import { tokens } from '../shared/tokens';
import BackgroundImagePicker from './components/BackgroundImagePicker';
import RefreshControl from './components/RefreshControl';
import UsageBar from './components/UsageBar';
import { useBackgroundImage } from './hooks/useBackgroundImage';
import { useUsage } from './hooks/useUsage';

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
              <UsageBar label="Current session" pct={usage.session_pct} resets={usage.session_resets} />
              <UsageBar label="Current week (all models)" pct={usage.week_pct} resets={usage.week_resets} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
