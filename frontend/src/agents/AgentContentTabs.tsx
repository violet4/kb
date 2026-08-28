import { tokens } from '../shared/tokens';
import DmChatPanel from '../channels/components/DmChatPanel';
import SessionTranscript from './chat/SessionTranscript';

export type AgentContentTab = 'chat' | 'session';

interface AgentContentTabsProps {
  agentSessionId: string;
  channelId: number | null;
  displayName: string;
  tab: AgentContentTab;
  onChangeTab: (tab: AgentContentTab) => void;
  onSent: () => void;
}

// The Chat/Session tab switch for one live agent -- shared by AgentPage's standalone
// /agents/:sessionId route and ChannelsView's own content pane, so clicking "view session
// transcript" from Channels can switch this same pane in place instead of navigating away
// and losing the channel sidebar (confirmed live 2026-08-28 as the actual complaint: the
// standalone-page navigation was correct in isolation but wrong from inside Channels, where
// the sidebar is the point of being there). "Chat" is the ChannelMessage DM mailbox; "Session"
// is the agent's own raw Claude Code transcript file -- see SessionTranscript's and
// DmChatPanel's own docstrings for why these must never be conflated into one view.
export default function AgentContentTabs({
  agentSessionId,
  channelId,
  displayName,
  tab,
  onChangeTab,
  onSent,
}: AgentContentTabsProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, flex: 1 }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${tokens.color.border}` }}>
        <TabButton label="Chat" isActive={tab === 'chat'} onClick={() => onChangeTab('chat')} />
        <TabButton label="Session" isActive={tab === 'session'} onClick={() => onChangeTab('session')} />
      </div>
      {tab === 'session' ? (
        <SessionTranscript sessionId={agentSessionId} />
      ) : (
        <DmChatPanel
          agentSessionId={agentSessionId}
          channelId={channelId}
          displayName={displayName}
          onSent={onSent}
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
