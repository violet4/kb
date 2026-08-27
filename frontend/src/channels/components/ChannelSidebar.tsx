import { tokens } from '../../shared/tokens';
import type { ChannelSummary } from '../types';

interface ChannelSidebarProps {
  channels: ChannelSummary[];
  selectedKey: string | null;
  onSelect: (channel: ChannelSummary) => void;
}

// A channel's row identity for selection -- agent_session_id for a DM (stable across the DM
// slot existing before any message has ever been sent, when channel_id is still null), the
// literal "broadcast" for the one broadcast row.
export function channelKey(channel: ChannelSummary): string {
  return channel.kind === 'broadcast' ? 'broadcast' : (channel.agent_session_id ?? '');
}

function timeAgo(iso: string | null): string {
  if (iso === null) return '';
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export default function ChannelSidebar({ channels, selectedKey, onSelect }: ChannelSidebarProps) {
  const broadcast = channels.find((c) => c.kind === 'broadcast');
  const dms = channels.filter((c) => c.kind === 'dm');

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        width: 260,
        flexShrink: 0,
        borderRight: `1px solid ${tokens.color.border}`,
        paddingRight: 16,
      }}
    >
      {broadcast && (
        <button
          type="button"
          onClick={() => onSelect(broadcast)}
          aria-current={selectedKey === channelKey(broadcast)}
          style={rowStyle(selectedKey === channelKey(broadcast))}
        >
          <span style={{ fontWeight: 600 }}>#broadcast</span>
          {broadcast.last_message_at && (
            <span style={{ fontSize: 11, color: tokens.color.textMuted }}>{timeAgo(broadcast.last_message_at)}</span>
          )}
        </button>
      )}
      <div>
        <div style={{ fontSize: 11, color: tokens.color.textMuted, padding: '4px 8px', textTransform: 'uppercase' }}>
          Live agents ({dms.length})
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {dms.map((dm) => (
            <button
              key={channelKey(dm)}
              type="button"
              onClick={() => onSelect(dm)}
              aria-current={selectedKey === channelKey(dm)}
              aria-label={`Open DM with ${dm.agent_session_id}`}
              style={rowStyle(selectedKey === channelKey(dm))}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', overflow: 'hidden' }}>
                <span style={{ fontFamily: 'monospace', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {dm.agent_session_id}
                </span>
                <span style={{ fontSize: 11, color: tokens.color.textMuted }}>{dm.agent_cwd}</span>
              </div>
              {dm.last_message_at && (
                <span style={{ fontSize: 11, color: tokens.color.textMuted, flexShrink: 0 }}>
                  {timeAgo(dm.last_message_at)}
                </span>
              )}
            </button>
          ))}
          {dms.length === 0 && (
            <p style={{ margin: 0, padding: '4px 8px', fontSize: 12, color: tokens.color.textMuted }}>
              No live agents.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function rowStyle(isSelected: boolean): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    width: '100%',
    padding: '6px 8px',
    borderRadius: 6,
    border: 'none',
    background: isSelected ? tokens.color.surface : 'transparent',
    color: tokens.color.text,
    fontSize: 13,
    textAlign: 'left',
    cursor: 'pointer',
  };
}
