import { Link } from 'react-router-dom';
import { tokens } from '../../shared/tokens';
import type { ChannelSummary } from '../types';

interface ChannelSidebarProps {
  channels: ChannelSummary[];
  selectedKey: string | null;
  onSelect: (channel: ChannelSummary) => void;
}

// A channel's row identity for selection -- agent_session_id for a DM (stable across the DM
// slot existing before any message has ever been sent, when channel_id is still null), the
// channel's own name for a named channel.
export function channelKey(channel: ChannelSummary): string {
  return channel.kind === 'named' ? `named:${channel.name}` : (channel.agent_session_id ?? '');
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

// Short label for a cwd section header -- last path segment ("kb", "img"), falling back to
// the full path if it has no separator. Purely a sidebar grouping aid (see this module's own
// design note in ChannelsView): agents sharing a cwd are not a Channel, just visually grouped.
function cwdLabel(cwd: string): string {
  const parts = cwd.split('/').filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : cwd;
}

export default function ChannelSidebar({ channels, selectedKey, onSelect }: ChannelSidebarProps) {
  const named = channels.filter((c) => c.kind === 'named');
  const dms = channels.filter((c) => c.kind === 'dm');

  const cwdGroups = new Map<string, ChannelSummary[]>();
  for (const dm of dms) {
    const group = cwdGroups.get(dm.agent_cwd) ?? [];
    group.push(dm);
    cwdGroups.set(dm.agent_cwd, group);
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        width: 260,
        flexShrink: 0,
        borderRight: `1px solid ${tokens.color.border}`,
        paddingRight: 16,
        overflowY: 'auto',
      }}
    >
      {named.length > 0 && (
        <div>
          <SectionHeader label="Channels" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {named.map((channel) => (
              <button
                key={channelKey(channel)}
                type="button"
                onClick={() => onSelect(channel)}
                aria-current={selectedKey === channelKey(channel)}
                style={rowStyle(selectedKey === channelKey(channel))}
              >
                <span style={{ fontWeight: 600 }}>#{channel.name}</span>
                {channel.last_message_at && (
                  <span style={{ fontSize: 11, color: tokens.color.textMuted }}>
                    {timeAgo(channel.last_message_at)}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {Array.from(cwdGroups.entries()).map(([cwd, agents]) => (
        <div key={cwd}>
          <SectionHeader label={cwdLabel(cwd)} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {agents.map((dm) => (
              <DmRow key={channelKey(dm)} dm={dm} isSelected={selectedKey === channelKey(dm)} onSelect={onSelect} />
            ))}
          </div>
        </div>
      ))}

      <div>
        <SectionHeader label={`All live agents (${dms.length})`} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {dms.map((dm) => (
            <DmRow key={channelKey(dm)} dm={dm} isSelected={selectedKey === channelKey(dm)} onSelect={onSelect} />
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

function SectionHeader({ label }: { label: string }) {
  return (
    <div style={{ fontSize: 11, color: tokens.color.textMuted, padding: '4px 8px', textTransform: 'uppercase' }}>
      {label}
    </div>
  );
}

function DmRow({
  dm,
  isSelected,
  onSelect,
}: {
  dm: ChannelSummary;
  isSelected: boolean;
  onSelect: (channel: ChannelSummary) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <button
        type="button"
        onClick={() => onSelect(dm)}
        aria-current={isSelected}
        aria-label={`Open DM with ${dm.agent_session_id}`}
        style={{ ...rowStyle(isSelected), flex: 1, minWidth: 0 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', overflow: 'hidden' }}>
          <span style={{ fontFamily: 'monospace', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {dm.agent_session_id}
          </span>
        </div>
        {dm.last_message_at && (
          <span style={{ fontSize: 11, color: tokens.color.textMuted, flexShrink: 0 }}>
            {timeAgo(dm.last_message_at)}
          </span>
        )}
      </button>
      {dm.agent_session_id && (
        <Link
          to={`/agents/${encodeURIComponent(dm.agent_session_id)}?tab=session`}
          aria-label={`View session transcript for ${dm.agent_session_id}`}
          title="View session transcript"
          style={{ color: tokens.color.textMuted, fontSize: 12, textDecoration: 'none', flexShrink: 0 }}
        >
          ⧉
        </Link>
      )}
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
