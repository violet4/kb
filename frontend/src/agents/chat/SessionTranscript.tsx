import { useCallback, useEffect, useMemo, useState } from 'react';
import { tokens } from '../../shared/tokens';
import { fetchSessionChat } from './api';
import { addressBlocks, type AddressedBlock } from './blockAddress';
import type { FacetFilter } from './facets';
import { useCollapseState } from './hooks/useCollapseState';
import LegendPanel, { filterBlocks } from './LegendPanel';
import type { ChatMessage } from './types';

function TagList({ tags }: { tags: Record<string, string> }) {
  return (
    <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 10px', margin: 0, fontSize: 11, minWidth: 0 }}>
      {Object.entries(tags).map(([key, value]) => (
        // minWidth: 0 + overflow-wrap on the value -- a long unbroken tag value (a full
        // path, a long id) would otherwise force this flex item wider than its container,
        // pushing the whole message column into horizontal scroll (confirmed live
        // 2026-08-28: the session transcript pane, not the legend, was the one actually
        // overflowing).
        <div key={key} style={{ display: 'flex', gap: 4, minWidth: 0, maxWidth: '100%' }}>
          <dt style={{ color: tokens.color.textMuted, flexShrink: 0 }}>{key}:</dt>
          <dd style={{ margin: 0, color: tokens.color.text, minWidth: 0, overflowWrap: 'break-word' }}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function BlockRow({
  addressed,
  collapsed,
  onToggle,
}: {
  addressed: AddressedBlock;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { block } = addressed;
  const summary =
    block.kind === 'tool_use'
      ? `tool_use: ${block.tool_name}`
      : block.kind === 'tool_result'
        ? `tool_result${block.is_error ? ' (error)' : ''}`
        : block.kind === 'unknown'
          ? 'unknown block'
          : 'text';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        aria-label={`Toggle ${summary} block ${addressed.id}`}
        style={{
          alignSelf: 'flex-start',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: 0,
          border: 'none',
          background: 'transparent',
          color: block.is_error ? tokens.color.danger : tokens.color.accent,
          fontSize: 12,
          cursor: 'pointer',
        }}
      >
        <span>{collapsed ? '▸' : '▾'}</span>
        <span>{summary}</span>
      </button>
      {!collapsed && (
        <>
          {block.kind === 'text' && (
            <p
              style={{
                margin: 0,
                fontSize: 14,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                color: tokens.color.text,
              }}
            >
              {block.text}
            </p>
          )}
          {block.kind === 'tool_use' && (
            <pre
              style={{
                margin: 0,
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                color: tokens.color.textMuted,
              }}
            >
              {JSON.stringify(block.tool_input, null, 2)}
            </pre>
          )}
          {block.kind === 'tool_result' && (
            <pre
              style={{
                margin: 0,
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                color: tokens.color.text,
              }}
            >
              {block.tool_output}
            </pre>
          )}
          <TagList tags={addressed.tags} />
        </>
      )}
    </div>
  );
}

function MessageRow({
  message,
  addressedBlocks,
  isCollapsed,
  onToggle,
}: {
  message: ChatMessage;
  addressedBlocks: AddressedBlock[];
  isCollapsed: (id: string) => boolean;
  onToggle: (id: string) => void;
}) {
  if (addressedBlocks.length === 0) return null;
  const isUser = message.role === 'user';
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${tokens.color.border}`,
        background: isUser ? tokens.color.surface : 'transparent',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: tokens.color.textMuted }}>
        <span style={{ fontWeight: 600, color: isUser ? tokens.color.accent : tokens.color.text }}>
          {message.role}
        </span>
        <span>{message.timestamp}</span>
      </div>
      {addressedBlocks.map((addressed) => (
        <BlockRow
          key={addressed.id}
          addressed={addressed}
          collapsed={isCollapsed(addressed.id)}
          onToggle={() => onToggle(addressed.id)}
        />
      ))}
    </div>
  );
}

interface SessionTranscriptProps {
  sessionId: string;
}

// The raw Claude Code JSONL transcript for one session -- every user/assistant message,
// tool_use/tool_result block, with the generic tag-filter legend. Distinct from a Channel DM
// (frontend/src/channels/): this reads the session's own transcript file, not the
// cross-session ChannelMessage mailbox -- see the two-tab split in AgentPage.tsx for why they
// must never be conflated into one view.
export default function SessionTranscript({ sessionId }: SessionTranscriptProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FacetFilter>(new Map());
  const [legendOpen, setLegendOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchSessionChat(sessionId)
      .then((result) => {
        if (!cancelled) setMessages(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const allBlocks = useMemo(() => addressBlocks(messages), [messages]);
  const visibleBlocks = useMemo(() => filterBlocks(allBlocks, filter), [allBlocks, filter]);
  const { isCollapsed, toggle, collapseMatching, expandMatching } = useCollapseState(allBlocks);

  const toggleFilterValue = useCallback((key: string, value: string) => {
    setFilter((prev) => {
      const next = new Map(prev);
      const values = new Set(next.get(key) ?? []);
      if (values.has(value)) values.delete(value);
      else values.add(value);
      next.set(key, values);
      return next;
    });
  }, []);

  const messageBlockGroups = useMemo(
    () => messages.map((_message, messageIndex) => visibleBlocks.filter((b) => b.messageIndex === messageIndex)),
    [messages, visibleBlocks],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, flex: 1 }}>
      {loading && <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>Loading...</p>}
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>No chat messages found.</p>
      )}
      {/* alignItems defaults to stretch (not flex-start) so both the message pane and the
          legend actually fill this row's real height -- with flex-start, each pane sized to
          its own content, meaning this row (and the page above it) grew to fit the taller of
          the two, defeating both panes' own overflowY: auto and pushing the whole PAGE into
          scroll instead of just the one pane that's actually long (confirmed live
          2026-08-28: a session with many distinct facet values made the legend taller than
          the viewport, and the page itself scrolled to show the rest of it). */}
      {/* position: relative so the collapsed-state expand tab (below) can float over this
          row as an absolutely-positioned overlay rather than reserving its own flex slice --
          confirmed live 2026-08-28 that even an ~8px-wide reserved rail still read as a
          visible "lost strip" on top of its own width once the inter-pane gap was counted;
          removing it from flow entirely (not just shrinking it) is the actual fix. */}
      <div style={{ display: 'flex', gap: legendOpen ? 16 : 0, flex: 1, minHeight: 0, position: 'relative' }}>
        {/* Its own scroll container, independent of the page (and, inside Channels, the left
            channel sidebar) -- overflowY here, not on some page-level wrapper, is what lets a
            long transcript scroll without taking the sidebar or legend along with it. */}
        <div style={{ flex: 1, minWidth: 0, height: '100%', overflowY: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {messages.map((message, i) => (
              <MessageRow
                key={i}
                message={message}
                addressedBlocks={messageBlockGroups[i]}
                isCollapsed={isCollapsed}
                onToggle={toggle}
              />
            ))}
          </div>
        </div>
        {allBlocks.length > 0 && legendOpen && (
          <div style={{ flex: '0 0 280px', height: '100%' }}>
            <LegendPanel
              allBlocks={allBlocks}
              visibleBlocks={visibleBlocks}
              filter={filter}
              onToggleFilterValue={toggleFilterValue}
              onClearFilter={() => setFilter(new Map())}
              onCollapseVisible={() => collapseMatching(visibleBlocks)}
              onExpandVisible={() => expandMatching(visibleBlocks)}
              onCollapsePanel={() => setLegendOpen(false)}
            />
          </div>
        )}
        {allBlocks.length > 0 && !legendOpen && (
          // Overlay tab, not a flex item -- takes zero width from the message pane. Sits
          // just inside the pane's own right edge (not the container's, since the message
          // pane spans the full row when the legend is collapsed) so it reads as a
          // hover/reveal affordance rather than a permanent UI slice.
          <button
            type="button"
            onClick={() => setLegendOpen(true)}
            aria-label="Expand filter legend"
            title="Expand filter legend"
            style={{
              position: 'absolute',
              top: 0,
              right: 8,
              padding: '6px 4px',
              borderRadius: 6,
              border: `1px solid ${tokens.color.border}`,
              background: tokens.color.surface,
              color: tokens.color.textMuted,
              fontSize: 12,
              cursor: 'pointer',
              opacity: 0.6,
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.6')}
          >
            ◂
          </button>
        )}
      </div>
    </div>
  );
}
