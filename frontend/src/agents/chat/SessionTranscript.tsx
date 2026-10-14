import { memo, useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Markdown from '../../shared/Markdown';
import { tokens } from '../../shared/tokens';
import { useRefreshIntervalSetting } from '../hooks/useRefreshIntervalSetting';
import type { AddressedBlock } from './blockAddress';
import type { FacetFilter } from './facets';
import { useCollapseState } from './hooks/useCollapseState';
import { useSessionChat, type TranscriptEntry } from './hooks/useSessionChat';
import LegendPanel, { filterBlocks } from './LegendPanel';
import type { ChatBlock, ChatMessage } from './types';

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

// A Bash tool call's command, shown as a command rather than inside its JSON input; whatever
// else the input carries (timeout, run_in_background, ...) stays as JSON, when there is any.
function bashInput(
  block: ChatBlock,
): { command: string; description: string | null; rest: Record<string, unknown> | null } | null {
  const input = block.tool_input;
  if (block.kind !== 'tool_use' || block.tool_name !== 'Bash' || typeof input?.command !== 'string') return null;
  const { command, description, ...rest } = input;
  return {
    command,
    description: typeof description === 'string' ? description : null,
    rest: Object.keys(rest).length > 0 ? rest : null,
  };
}

// Collapsed blocks still show the command, clipped to its first lines, since a session is read
// mostly by what it ran; expanding shows all of it.
const BASH_PREVIEW_LINES = 6;

function BashCommand({ command, description, full }: { command: string; description: string | null; full: boolean }) {
  const lines = command.split('\n');
  const hidden = full ? 0 : Math.max(0, lines.length - BASH_PREVIEW_LINES);
  const shown = hidden ? lines.slice(0, BASH_PREVIEW_LINES).join('\n') : command;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {description && <span style={{ fontSize: 12, color: tokens.color.textMuted }}>{description}</span>}
      <pre
        style={{
          margin: 0,
          padding: '6px 8px',
          fontSize: 12,
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
          background: tokens.color.background,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          color: tokens.color.text,
        }}
      >
        {shown}
      </pre>
      {hidden > 0 && (
        <span style={{ fontSize: 11, color: tokens.color.textMuted }}>
          … {hidden} more line{hidden === 1 ? '' : 's'} (expand to see all)
        </span>
      )}
    </div>
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
  const bash = bashInput(block);
  const summary =
    block.kind === 'tool_use'
      ? `tool_use: ${block.tool_name}`
      : block.kind === 'tool_result'
        ? `tool_result${block.is_error ? ' (error)' : ''}`
        : block.kind === 'unknown'
          ? 'unknown block'
          : block.kind;

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
      {bash && <BashCommand command={bash.command} description={bash.description} full={!collapsed} />}
      {!collapsed && (
        <>
          {block.kind === 'text' && <Markdown text={block.text ?? ''} />}
          {block.kind === 'thinking' && (
            <Markdown text={block.text ?? ''} color={tokens.color.thinking} />
          )}
          {block.kind === 'tool_use' && (!bash || bash.rest) && (
            <pre
              style={{
                margin: 0,
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                color: tokens.color.textMuted,
              }}
            >
              {JSON.stringify(bash ? bash.rest : block.tool_input, null, 2)}
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

// Renders one addressed block as markdown, matching what BlockRow shows on screen (text as
// its raw markdown, tool_use/tool_result as fenced code blocks) so "copy as markdown" round
// trips what's actually visible rather than a separate serialization.
function blockToMarkdown(addressed: AddressedBlock): string {
  const { block } = addressed;
  if (block.kind === 'text') return block.text ?? '';
  if (block.kind === 'thinking') return `**thinking**\n\n${block.text ?? ''}`;
  const bash = bashInput(block);
  if (bash) {
    const description = bash.description ? `\n${bash.description}` : '';
    const rest = bash.rest ? `\n\`\`\`json\n${JSON.stringify(bash.rest, null, 2)}\n\`\`\`` : '';
    return `**tool_use: Bash**${description}\n\`\`\`bash\n${bash.command}\n\`\`\`${rest}`;
  }
  if (block.kind === 'tool_use') {
    return `**tool_use: ${block.tool_name}**\n\`\`\`json\n${JSON.stringify(block.tool_input, null, 2)}\n\`\`\``;
  }
  if (block.kind === 'tool_result') {
    return `**tool_result${block.is_error ? ' (error)' : ''}**\n\`\`\`\n${block.tool_output ?? ''}\n\`\`\``;
  }
  return '';
}

function messageToMarkdown(message: ChatMessage, addressedBlocks: AddressedBlock[]): string {
  const header = `**${message.role}** — ${message.timestamp}`;
  const body = addressedBlocks.map(blockToMarkdown).filter(Boolean).join('\n\n');
  return [header, body].filter(Boolean).join('\n\n');
}

function CopyMarkdownButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(getText()).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      title="Copy message as markdown"
      style={{
        padding: '2px 6px',
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 4,
        background: 'transparent',
        color: tokens.color.textMuted,
        fontSize: 11,
        cursor: 'pointer',
      }}
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

// Memoized so a live transcript's appended messages render only the new rows: an existing
// row's props (its entry, the filter, the collapse callbacks) are unchanged by an append, so
// React skips it and leaves its DOM, and any text selection inside it, untouched.
const MessageRow = memo(function MessageRow({
  entry,
  filter,
  isCollapsed,
  onToggle,
}: {
  entry: TranscriptEntry;
  filter: FacetFilter;
  isCollapsed: (block: AddressedBlock) => boolean;
  onToggle: (block: AddressedBlock) => void;
}) {
  const { message } = entry;
  const addressedBlocks = useMemo(() => filterBlocks(entry.blocks, filter), [entry.blocks, filter]);
  if (addressedBlocks.length === 0) return null;
  const isUser = message.role === 'user';
  const isHuman = isUser && isHumanText(message);
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${tokens.color.border}`,
        background: isHuman ? tokens.color.humanMessage : isUser ? tokens.color.surface : 'transparent',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: tokens.color.textMuted }}>
        <span style={{ fontWeight: 600, color: isUser ? tokens.color.accent : tokens.color.text }}>
          {message.role}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{message.timestamp}</span>
          <CopyMarkdownButton getText={() => messageToMarkdown(message, addressedBlocks)} />
        </div>
      </div>
      {addressedBlocks.map((addressed) => (
        <BlockRow
          key={addressed.id}
          addressed={addressed}
          collapsed={isCollapsed(addressed)}
          onToggle={() => onToggle(addressed)}
        />
      ))}
    </div>
  );
});

// Text a person typed, as opposed to a tool result or text the harness injected (isMeta) on the user's turn.
function isHumanText(message: ChatMessage): boolean {
  return message.blocks.some((b) => b.kind === 'text' && b.tags.isMeta !== 'true');
}

// Distance from the bottom, in pixels, within which the message pane counts as scrolled to
// the bottom and keeps following new messages.
const FOLLOW_THRESHOLD_PX = 40;

interface SessionTranscriptProps {
  sessionId: string;
}

// The raw Claude Code JSONL transcript for one session -- every user/assistant message,
// tool_use/tool_result block, with the generic tag-filter legend. Distinct from a Channel DM
// (frontend/src/channels/): this reads the session's own transcript file, not the
// cross-session ChannelMessage mailbox -- see the two-tab split in AgentPage.tsx for why they
// must never be conflated into one view. A live session's new messages are appended at the
// bottom as they are written (see useSessionChat); while the message pane is scrolled to the
// bottom it follows them.
export default function SessionTranscript({ sessionId }: SessionTranscriptProps) {
  const [intervalSeconds] = useRefreshIntervalSetting();
  const { entries, loading, error } = useSessionChat(sessionId, intervalSeconds);
  const [filter, setFilter] = useState<FacetFilter>(new Map());
  const [legendOpen, setLegendOpen] = useState(false);

  const allBlocks = useMemo(() => entries.flatMap((entry) => entry.blocks), [entries]);
  const visibleBlocks = useMemo(() => filterBlocks(allBlocks, filter), [allBlocks, filter]);
  const { isCollapsed, toggle, collapseMatching, expandMatching } = useCollapseState();

  // Whether the pane was at the bottom before the latest render, updated on every scroll.
  // Read in the layout effect below, after new rows are in the DOM but before paint, so a
  // follow scroll never shows a frame of the old position.
  const paneRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(false);
  const seenCountRef = useRef(0);
  const onPaneScroll = useCallback(() => {
    const pane = paneRef.current;
    if (pane) followRef.current = pane.scrollHeight - pane.scrollTop - pane.clientHeight <= FOLLOW_THRESHOLD_PX;
  }, []);
  useLayoutEffect(() => {
    const previousCount = seenCountRef.current;
    seenCountRef.current = entries.length;
    // The first load opens at the top of the transcript; only later appends follow.
    if (previousCount === 0 || entries.length <= previousCount) return;
    const pane = paneRef.current;
    if (pane && followRef.current) pane.scrollTop = pane.scrollHeight;
  }, [entries]);

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, flex: 1 }}>
      {loading && <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>Loading...</p>}
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && entries.length === 0 && (
        <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>No chat messages found.</p>
      )}
      {/* alignItems defaults to stretch (not flex-start) so both the message pane and the
          legend fill this row's bounded height and scroll independently of each other and
          of the page; with flex-start each pane sizes to its own content and the page
          scrolls instead. */}
      {/* position: relative so the collapsed-state expand tab (below) floats over this row
          as an absolutely positioned overlay instead of reserving its own flex slice, which
          reads as a lost strip beside the messages. */}
      <div style={{ display: 'flex', gap: legendOpen ? 16 : 0, flex: 1, minHeight: 0, position: 'relative' }}>
        <div ref={paneRef} onScroll={onPaneScroll} style={{ flex: 1, minWidth: 0, height: '100%', overflowY: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {entries.map((entry, i) => (
              <MessageRow
                key={i}
                entry={entry}
                filter={filter}
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
          // Overlay tab, not a flex item -- takes zero width from the message pane. Anchored
          // to this bounded row rather than to the scrolling content, so it stays in view at
          // any scroll position; inset from the right edge to clear the pane's scrollbar.
          <button
            type="button"
            onClick={() => setLegendOpen(true)}
            aria-label="Expand filter legend"
            title="Expand filter legend"
            style={{
              position: 'absolute',
              top: 0,
              right: 16,
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
