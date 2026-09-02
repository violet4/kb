import { useMemo } from 'react';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import AgentContentTabs, { type AgentContentTab } from './AgentContentTabs';
import { useChannelList } from '../channels/hooks/useChannelList';
import { useChannelListRefreshInterval } from '../channels/hooks/useChannelListRefreshInterval';
import { tokens } from '../shared/tokens';
import { useDisplayName } from '../shared/useDisplayName';

// One live agent's standalone page (linked from the Agents table), switchable between Chat
// and Session -- see AgentContentTabs for what each tab means. Defaults to "session" so this
// URL keeps behaving exactly as it did before it grew a Chat tab.
export default function AgentPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: AgentContentTab = searchParams.get('tab') === 'chat' ? 'chat' : 'session';

  // Set by AgentHistoryView's session links (via Link's `state` prop) so a session opened
  // from the past-sessions drilldown returns there instead of always landing on the live
  // Agents table -- state, not a query param, since this is navigation-origin metadata, not
  // shareable/bookmarkable URL state.
  const location = useLocation();
  const fromHistoryProject = (location.state as { fromHistoryProject?: string } | null)?.fromHistoryProject;
  const backHref = fromHistoryProject ? `/agents/history/${encodeURIComponent(fromHistoryProject)}` : '/agents';
  const backLabel = fromHistoryProject ? '← Project' : '← Agents';

  const [displayName] = useDisplayName();
  const [intervalSeconds] = useChannelListRefreshInterval();
  const { channels, refresh: refreshChannels } = useChannelList(displayName, intervalSeconds);
  const dmChannel = useMemo(
    () => channels.find((c) => c.kind === 'dm' && c.agent_session_id === sessionId) ?? null,
    [channels, sessionId],
  );
  const channelId = dmChannel?.channel_id ?? null;

  function setTab(next: AgentContentTab) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set('tab', next);
      return params;
    });
  }

  if (!sessionId) return null;

  return (
    // flex: 1 + minHeight: 0 (not a hardcoded calc(100vh - Npx)) for the same reason as
    // ChannelsView's own layout -- see that component's comment. Only applied for the Chat
    // tab, which needs a bounded height to scroll internally; the Session tab keeps its
    // legacy behavior of letting the whole page grow/scroll naturally.
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        flex: tab === 'chat' ? 1 : undefined,
        minHeight: tab === 'chat' ? 0 : undefined,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Link to={backHref} style={{ color: tokens.color.textMuted, fontSize: 13, textDecoration: 'none' }}>
          {backLabel}
        </Link>
        <h1 style={{ margin: 0, fontSize: 18, fontFamily: 'monospace' }} title={sessionId}>
          {dmChannel?.agent_title || sessionId}
        </h1>
      </div>
      <AgentContentTabs
        agentSessionId={sessionId}
        channelId={channelId}
        displayName={displayName}
        tab={tab}
        onChangeTab={setTab}
        onSent={refreshChannels}
      />
    </div>
  );
}
