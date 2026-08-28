import { useMemo } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import SessionTranscript from './chat/SessionTranscript';
import DmChatPanel from '../channels/components/DmChatPanel';
import { useChannelList } from '../channels/hooks/useChannelList';
import { useChannelListRefreshInterval } from '../channels/hooks/useChannelListRefreshInterval';
import { tokens } from '../shared/tokens';
import { useDisplayName } from '../shared/useDisplayName';

type Tab = 'chat' | 'session';

// One live agent's page, switchable between two genuinely distinct data sources that must
// never be conflated (see the 2026-08-27 chat/session-transcript confusion this tab split
// resolves): "Chat" is the ChannelMessage DM mailbox (kb sessions send-equivalent, delivered
// whenever the agent next checks its inbox/listener); "Session" is that agent's own raw
// Claude Code transcript file, read-only, with no notion of "delivery" at all. Defaults to
// "session" so the standalone /agents/:sessionId link (from the Agents table) keeps behaving
// exactly as it did before this page grew a Chat tab.
export default function AgentPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: Tab = searchParams.get('tab') === 'chat' ? 'chat' : 'session';

  const [displayName] = useDisplayName();
  const [intervalSeconds] = useChannelListRefreshInterval();
  const { channels, refresh: refreshChannels } = useChannelList(displayName, intervalSeconds);
  const channelId = useMemo(
    () => channels.find((c) => c.kind === 'dm' && c.agent_session_id === sessionId)?.channel_id ?? null,
    [channels, sessionId],
  );

  function setTab(next: Tab) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set('tab', next);
      return params;
    });
  }

  if (!sessionId) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: tab === 'chat' ? 'calc(100vh - 96px)' : undefined }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Link to="/agents" style={{ color: tokens.color.textMuted, fontSize: 13, textDecoration: 'none' }}>
          ← Agents
        </Link>
        <h1 style={{ margin: 0, fontSize: 18, fontFamily: 'monospace' }}>{sessionId}</h1>
      </div>
      <div style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${tokens.color.border}` }}>
        <TabButton label="Session" isActive={tab === 'session'} onClick={() => setTab('session')} />
        <TabButton label="Chat" isActive={tab === 'chat'} onClick={() => setTab('chat')} />
      </div>
      {tab === 'session' ? (
        <SessionTranscript sessionId={sessionId} />
      ) : (
        <DmChatPanel
          agentSessionId={sessionId}
          channelId={channelId}
          displayName={displayName}
          onSent={refreshChannels}
        />
      )}
    </div>
  );
}

function TabButton({ label, isActive, onClick }: { label: string; isActive: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={isActive}
      style={{
        padding: '8px 14px',
        border: 'none',
        borderBottom: `2px solid ${isActive ? tokens.color.accent : 'transparent'}`,
        background: 'transparent',
        color: isActive ? tokens.color.text : tokens.color.textMuted,
        fontSize: 13,
        fontWeight: isActive ? 600 : 400,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}
