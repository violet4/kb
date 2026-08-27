import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { tokens } from '../../shared/tokens';
import { fetchSessionChat } from './api';
import { addressBlocks, type AddressedBlock } from './blockAddress';
import type { FacetFilter } from './facets';
import { useCollapseState } from './hooks/useCollapseState';
import LegendPanel, { filterBlocks } from './LegendPanel';
import type { ChatMessage } from './types';

function TagList({ tags }: { tags: Record<string, string> }) {
  return (
    <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 10px', margin: 0, fontSize: 11 }}>
      {Object.entries(tags).map(([key, value]) => (
        <div key={key} style={{ display: 'flex', gap: 4 }}>
          <dt style={{ color: tokens.color.textMuted }}>{key}:</dt>
          <dd style={{ margin: 0, color: tokens.color.text }}>{value}</dd>
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
            <p style={{ margin: 0, fontSize: 14, whiteSpace: 'pre-wrap', color: tokens.color.text }}>{block.text}</p>
          )}
          {block.kind === 'tool_use' && (
            <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap', color: tokens.color.textMuted }}>
              {JSON.stringify(block.tool_input, null, 2)}
            </pre>
          )}
          {block.kind === 'tool_result' && (
            <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap', color: tokens.color.text }}>
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

export default function SessionChatView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FacetFilter>(new Map());

  useEffect(() => {
    if (!sessionId) return;
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Link to="/agents" style={{ color: tokens.color.textMuted, fontSize: 13, textDecoration: 'none' }}>
          ← Agents
        </Link>
        <h1 style={{ margin: 0, fontSize: 18, fontFamily: 'monospace' }}>{sessionId}</h1>
      </div>
      {loading && <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>Loading...</p>}
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>No chat messages found.</p>
      )}
      {allBlocks.length > 0 && (
        <LegendPanel
          allBlocks={allBlocks}
          visibleBlocks={visibleBlocks}
          filter={filter}
          onToggleFilterValue={toggleFilterValue}
          onClearFilter={() => setFilter(new Map())}
          onCollapseVisible={() => collapseMatching(visibleBlocks)}
          onExpandVisible={() => expandMatching(visibleBlocks)}
        />
      )}
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
  );
}
