import { tokens } from '../../shared/tokens';
import { sendDirectMessage } from '../api';
import { useChannelMessages } from '../hooks/useChannelMessages';
import MessageComposer from './MessageComposer';
import MessageList from './MessageList';

interface DmChatPanelProps {
  agentSessionId: string;
  channelId: number | null;
  displayName: string;
  onSent: () => void; // lets the caller refresh its own channel-list state (channel_id may
  // have just been created for the first time) without this panel needing to know about it
}

// The DM-chat half of a live agent's page -- reused by both ChannelsView's own single-column
// layout and AgentPage's Chat tab, so the two surfaces can never drift on how a DM is
// rendered/sent from.
export default function DmChatPanel({ agentSessionId, channelId, displayName, onSent }: DmChatPanelProps) {
  const { messages, hasMoreOlder, loadingOlder, error, loadOlder, refresh } = useChannelMessages(channelId);

  async function handleSend(body: string) {
    await sendDirectMessage(displayName, agentSessionId, body);
    refresh();
    onSent();
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {error && <p style={{ margin: '8px 0', color: tokens.color.danger }}>{error}</p>}
      <MessageList
        messages={messages}
        channelExists={channelId !== null}
        selfSessionId={`human:${displayName}`}
        hasMoreOlder={hasMoreOlder}
        loadingOlder={loadingOlder}
        onLoadOlder={loadOlder}
      />
      <MessageComposer onSend={handleSend} placeholder="Message this agent..." />
    </div>
  );
}
