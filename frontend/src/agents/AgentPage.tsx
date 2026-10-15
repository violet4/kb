import { pageTitle, useDocumentTitle } from '../shared/useDocumentTitle';
import { useCallback, useEffect, useMemo } from 'react';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import AgentContentTabs, { AgentTabBar, type AgentContentTab } from './AgentContentTabs';
import Popover from '../shared/Popover';
import BarColorSetting from './BarColorSetting';
import { interruptSession, sendSessionInput } from './api';
import InterruptButton from './InterruptButton';
import MessageComposer from '../channels/components/MessageComposer';
import { formatSeconds } from './formatSeconds';
import { useAgentSessions } from './hooks/useAgentSessions';
import { useRefreshIntervalSetting } from './hooks/useRefreshIntervalSetting';
import { useTranscriptSettings } from './hooks/useTranscriptSettings';
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
  const {
    showTags,
    setShowTags,
    showThinking,
    setShowThinking,
    collapsedAsBars,
    setCollapsedAsBars,
    barColor,
    setBarColor,
    collapseBash,
    setCollapseBash,
  } = useTranscriptSettings();
  const [intervalSeconds] = useChannelListRefreshInterval();
  const { channels, refresh: refreshChannels } = useChannelList(displayName, intervalSeconds);
  const dmChannel = useMemo(
    () => channels.find((c) => c.kind === 'dm' && c.agent_session_id === sessionId) ?? null,
    [channels, sessionId],
  );
  const channelId = dmChannel?.channel_id ?? null;

  // Present only while the session is live: the same polled list as the Agents table's
  // Current tab, so the header's age matches the table's.
  const [agentsIntervalSeconds] = useRefreshIntervalSetting();
  const { sessions: liveSessions, refresh: refreshLiveSessions } = useAgentSessions(agentsIntervalSeconds);
  const liveSession = liveSessions.find((s) => s.id === sessionId) ?? null;

  const interrupt = useCallback(async () => {
    if (!sessionId) return;
    await interruptSession(sessionId);
    refreshLiveSessions();
  }, [sessionId, refreshLiveSessions]);

  // Escape anywhere on the Session tab presses Esc in the session, as it would in its terminal.
  // An open popover or dialog takes Escape first (closing it), and so does text mid-composition
  // in an input method.
  const canInterrupt = tab === 'session' && liveSession !== null && liveSession.interrupt_blocker === null;
  useEffect(() => {
    if (!canInterrupt) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Escape' || e.isComposing || e.defaultPrevented) return;
      if (document.querySelector(':popover-open, dialog[open]')) return;
      interrupt().catch(() => {}); // the Esc button shows failures; the next poll shows the state
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [canInterrupt, interrupt]);
  useDocumentTitle(pageTitle('agents', liveSession?.title || dmChannel?.agent_title || (sessionId ?? '').slice(0, 8)));

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
    // ChannelsView's own layout -- see that component's comment. Both tabs need the bounded
    // height: Chat scrolls its message list internally, and Session scrolls its
    // transcript.
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          minWidth: 0,
          borderBottom: `1px solid ${tokens.color.border}`,
        }}
      >
        <Link
          to={backHref}
          style={{ flexShrink: 0, color: tokens.color.textMuted, fontSize: 13, textDecoration: 'none' }}
        >
          {backLabel}
        </Link>
        <AgentTabBar tab={tab} onChangeTab={setTab} />
        <h1
          style={{
            margin: 0,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontSize: 18,
            fontFamily: 'monospace',
          }}
          title={sessionId}
        >
          {liveSession?.title || dmChannel?.agent_title || sessionId}
        </h1>
        {liveSession && (
          <span
            title={`Live session, registered ${formatSeconds(liveSession.age_seconds)} ago`}
            style={{
              padding: '1px 8px',
              borderRadius: 10,
              border: `1px solid ${tokens.color.border}`,
              color: tokens.color.textMuted,
              fontSize: 12,
            }}
          >
            age {formatSeconds(liveSession.age_seconds)}
          </span>
        )}
        <Link
          to={`/contexts?session=${encodeURIComponent(sessionId)}`}
          title="The Contexts page, narrowed to the kb records this session has read or changed"
          style={{ ...tokens.link, fontSize: 13 }}
        >
          contexts
        </Link>
        {tab === 'session' && (
          // A popover, not a modal, so the transcript stays visible while a setting changes it.
          <Popover label="⚙" align="end" ariaLabel="Transcript display settings" title="Transcript display settings">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={settingStyle}>
                <input type="checkbox" checked={showThinking} onChange={(e) => setShowThinking(e.target.checked)} />
                Show thinking
              </label>
              <label style={settingStyle}>
                <input type="checkbox" checked={showTags} onChange={(e) => setShowTags(e.target.checked)} />
                Show transcript fields
              </label>
              <label style={settingStyle}>
                <input type="checkbox" checked={collapseBash} onChange={(e) => setCollapseBash(e.target.checked)} />
                Collapse Bash commands
              </label>
              <label style={settingStyle}>
                <input
                  type="checkbox"
                  checked={collapsedAsBars}
                  onChange={(e) => setCollapsedAsBars(e.target.checked)}
                />
                Collapsed cards as bars
              </label>
              {collapsedAsBars && <BarColorSetting value={barColor} onChange={setBarColor} />}
            </div>
          </Popover>
        )}
      </div>
      <AgentContentTabs
        hideTabBar
        agentSessionId={sessionId}
        channelId={channelId}
        displayName={displayName}
        tab={tab}
        onChangeTab={setTab}
        onSent={refreshChannels}
        isLive={liveSession !== null}
      />
      {tab === 'session' && liveSession && (
        <MessageComposer
          onSend={async (text) => {
            await sendSessionInput(sessionId, text);
            refreshLiveSessions();
          }}
          placeholder="Prompt this session (Ctrl+Enter to send)"
          sendOnModEnter
          disabledReason={liveSession.prompt_blocker}
          actions={<InterruptButton onInterrupt={interrupt} blocker={liveSession.interrupt_blocker} />}
        />
      )}
    </div>
  );
}

const settingStyle = { display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, whiteSpace: 'nowrap' } as const;
