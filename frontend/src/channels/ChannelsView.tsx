import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import AgentContentTabs, { type AgentContentTab } from '../agents/AgentContentTabs';
import { tokens } from '../shared/tokens';
import { useDisplayName } from '../shared/useDisplayName';
import { sendToNamedChannel } from './api';
import ChannelSidebar, { channelKey } from './components/ChannelSidebar';
import MessageComposer from './components/MessageComposer';
import MessageList from './components/MessageList';
import { useChannelList } from './hooks/useChannelList';
import { useChannelListRefreshInterval } from './hooks/useChannelListRefreshInterval';
import { useChannelMessages } from './hooks/useChannelMessages';

function SettingsSection({
  displayName,
  onChangeDisplayName,
  intervalSeconds,
  onChangeIntervalSeconds,
}: {
  displayName: string;
  onChangeDisplayName: (value: string) => void;
  intervalSeconds: number;
  onChangeIntervalSeconds: (value: number) => void;
}) {
  return (
    <details style={{ fontSize: 13, color: tokens.color.textMuted }}>
      <summary style={{ cursor: 'pointer' }}>Settings</summary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label htmlFor="display-name">Your name</label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => onChangeDisplayName(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label htmlFor="channel-refresh-interval">Channel list refresh (seconds)</label>
          <input
            id="channel-refresh-interval"
            type="number"
            min={1}
            step={1}
            value={intervalSeconds}
            onChange={(e) => {
              const value = Number(e.target.value);
              if (value > 0) onChangeIntervalSeconds(value);
            }}
            style={{ ...inputStyle, width: 70 }}
          />
        </div>
      </div>
    </details>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '4px 8px',
  borderRadius: 6,
  border: `1px solid ${tokens.color.border}`,
  background: tokens.color.surface,
  color: tokens.color.text,
};

function NamedChannelPanel({
  name,
  channelId,
  displayName,
}: {
  name: string;
  channelId: number;
  displayName: string;
}) {
  const { messages, hasMoreOlder, loadingOlder, error, loadOlder, refresh } = useChannelMessages(channelId);

  async function handleSend(body: string) {
    await sendToNamedChannel(displayName, name, body);
    refresh();
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {error && <p style={{ margin: '8px 0', color: tokens.color.danger }}>{error}</p>}
      <MessageList
        messages={messages}
        channelExists
        selfSessionId={`human:${displayName}`}
        hasMoreOlder={hasMoreOlder}
        loadingOlder={loadingOlder}
        onLoadOlder={loadOlder}
      />
      <MessageComposer onSend={handleSend} placeholder={`Message #${name}...`} />
    </div>
  );
}

export default function ChannelsView() {
  const [displayName, setDisplayName] = useDisplayName();
  const [intervalSeconds, setIntervalSeconds] = useChannelListRefreshInterval();
  const { channels, error: channelsError, refresh: refreshChannels } = useChannelList(displayName, intervalSeconds);
  // Selected channel and tab live in the URL (?channel=..., ?tab=...), not component state,
  // so a page refresh (or a shared/bookmarked link) lands back on the same channel/tab --
  // the same reasoning AgentPage already applies to its own tab. selectedKey mirrors
  // ChannelSidebar's own channelKey() encoding (an agent_session_id for a DM, "named:<name>"
  // for a named channel) so the URL param and the sidebar's row-identity logic never drift.
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedKey = searchParams.get('channel');
  const contentTab: AgentContentTab = searchParams.get('tab') === 'session' ? 'session' : 'chat';

  const selected = useMemo(() => channels.find((c) => channelKey(c) === selectedKey) ?? null, [channels, selectedKey]);

  function selectChannel(key: string) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set('channel', key);
      params.delete('tab'); // switching channels always lands back on the default tab (Chat)
      return params;
    });
  }

  function setContentTab(next: AgentContentTab) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set('tab', next);
      return params;
    });
  }

  return (
    // Bleeds past App.tsx's page-level 24px padding on left/right/bottom -- unlike every
    // other route, this page's whole point is a dense two-pane layout that wants the full
    // viewport, not a reading-width-capped column with breathing room on every side. Negative
    // margin cancels that padding with NO compensating padding of its own: an 8px
    // paddingLeft/Right was tried first as "breathing room," but it visually read as its own
    // lost strip sitting flush against the legend panel's border on the right (confirmed live
    // via a high-contrast debug outline overlay, 2026-08-28 -- a bright yellow background made
    // an 8px gap between the legend's border and the true viewport edge obvious in a
    // screenshot where it hadn't been visible at normal contrast). marginBottom follows the
    // same reasoning -- the initial fix only canceled left/right and missed that the same
    // padding: 24 applies equally to the bottom edge, confirmed live as the same kind of
    // dead-space band running the full width at the bottom of the viewport. Any breathing
    // room belongs inside the sidebar/content children themselves, not as page-level padding
    // that eats into content on a page whose whole point is using the full space.
    //
    // Vertically: flex: 1 + minHeight: 0 against App.tsx's own flex-column + height: 100vh
    // wrapper, not a hardcoded calc(100vh - Npx) -- that calc assumed a top-offset that didn't
    // match this page's real chrome height and left ~30px of dead space at the bottom
    // (confirmed live 2026-08-28 via getBoundingClientRect on the rendered page).
    //
    // overflow: hidden here (this page's every scroll area is already its own internal
    // overflowY: auto pane -- the message list, the legend, the left sidebar) stops a
    // sub-pixel rounding overflow (confirmed live: this root's scrollHeight was 862 against a
    // clientHeight of 860, a 2px overflow from flex gap/border rounding) from ever reaching
    // App.tsx's shared ancestor and triggering ITS scrollbar gutter reservation there --
    // that gutter (~15px) was the actual remaining "gap on the right," confirmed via
    // getBoundingClientRect showing this root 15px narrower than the viewport despite the
    // negative-margin fix already being in effect.
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        flex: 1,
        minHeight: 0,
        marginLeft: -24,
        marginRight: -24,
        marginBottom: -24,
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Channels</h1>
        <SettingsSection
          displayName={displayName}
          onChangeDisplayName={setDisplayName}
          intervalSeconds={intervalSeconds}
          onChangeIntervalSeconds={setIntervalSeconds}
        />
      </div>
      {channelsError && <p style={{ margin: 0, color: tokens.color.danger }}>{channelsError}</p>}
      <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
        <ChannelSidebar
          channels={channels}
          selectedKey={selectedKey}
          onSelect={(c) => selectChannel(channelKey(c))}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0 }}>
          {selected === null ? (
            <p style={{ margin: 'auto', color: tokens.color.textMuted, fontSize: 13 }}>
              Select a channel to view its history.
            </p>
          ) : selected.kind === 'named' && selected.channel_id !== null ? (
            <>
              <div style={{ fontWeight: 600, fontSize: 14, paddingBottom: 8, borderBottom: `1px solid ${tokens.color.border}` }}>
                #{selected.name}
              </div>
              <NamedChannelPanel name={selected.name ?? ''} channelId={selected.channel_id} displayName={displayName} />
            </>
          ) : selected.kind === 'dm' && selected.agent_session_id ? (
            <AgentContentTabs
              agentSessionId={selected.agent_session_id}
              channelId={selected.channel_id}
              displayName={displayName}
              tab={contentTab}
              onChangeTab={setContentTab}
              onSent={refreshChannels}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
