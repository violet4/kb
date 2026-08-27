import { useMemo, useState } from 'react';
import { tokens } from '../shared/tokens';
import { useDisplayName } from '../shared/useDisplayName';
import { sendBroadcastMessage, sendDirectMessage } from './api';
import ChannelSidebar, { channelKey } from './components/ChannelSidebar';
import MessageComposer from './components/MessageComposer';
import MessageList from './components/MessageList';
import { useChannelList } from './hooks/useChannelList';
import { useChannelListRefreshInterval } from './hooks/useChannelListRefreshInterval';
import { useChannelMessages } from './hooks/useChannelMessages';
import type { ChannelSummary } from './types';

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

export default function ChannelsView() {
  const [displayName, setDisplayName] = useDisplayName();
  const [intervalSeconds, setIntervalSeconds] = useChannelListRefreshInterval();
  const { channels, error: channelsError } = useChannelList(displayName, intervalSeconds);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selected = useMemo(() => channels.find((c) => channelKey(c) === selectedKey) ?? null, [channels, selectedKey]);
  const { messages, hasMoreOlder, loadingOlder, error: messagesError, loadOlder } = useChannelMessages(
    selected?.channel_id ?? null,
  );

  async function handleSend(body: string) {
    if (selected === null) return;
    if (selected.kind === 'broadcast') {
      await sendBroadcastMessage(displayName, body);
    } else if (selected.agent_session_id) {
      await sendDirectMessage(displayName, selected.agent_session_id, body);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 96px)' }}>
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
        <ChannelSidebar channels={channels} selectedKey={selectedKey} onSelect={(c) => setSelectedKey(channelKey(c))} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {selected === null ? (
            <p style={{ margin: 'auto', color: tokens.color.textMuted, fontSize: 13 }}>
              Select a channel to view its history.
            </p>
          ) : (
            <>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  paddingBottom: 8,
                  borderBottom: `1px solid ${tokens.color.border}`,
                }}
              >
                {selected.kind === 'broadcast' ? '#broadcast' : selected.agent_session_id}
              </div>
              {messagesError && <p style={{ margin: '8px 0', color: tokens.color.danger }}>{messagesError}</p>}
              <MessageList
                messages={messages}
                selfSessionId={`human:${displayName}`}
                hasMoreOlder={hasMoreOlder}
                loadingOlder={loadingOlder}
                onLoadOlder={loadOlder}
              />
              <MessageComposer
                onSend={handleSend}
                placeholder={selected.kind === 'broadcast' ? 'Message #broadcast...' : 'Message this agent...'}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
