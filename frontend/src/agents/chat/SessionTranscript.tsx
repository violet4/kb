import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Markdown from '../../shared/Markdown';
import { tokens } from '../../shared/tokens';
import { useRefreshIntervalSetting } from '../hooks/useRefreshIntervalSetting';
import { useTranscriptSettings } from '../hooks/useTranscriptSettings';
import type { AddressedBlock } from './blockAddress';
import { defaultCollapsed, useCollapseState } from './hooks/useCollapseState';
import { NONE_HUNG, useHungToolCalls } from './hooks/useHungToolCalls';
import { useSessionChat, type TranscriptEntry } from './hooks/useSessionChat';
import { formatCallDuration, toolCallTimes, type ToolCallTime } from './toolCallTimes';
import type { ChatBlock, ChatMessage } from './types';

function TagList({ tags }: { tags: Record<string, string> }) {
  return (
    <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 10px', margin: 0, fontSize: 11, minWidth: 0 }}>
      {Object.entries(tags).map(([key, value]) => (
        // minWidth: 0 + overflow-wrap on the value -- a long unbroken tag value (a full
        // path, a long id) would otherwise force this flex item wider than its container,
        // pushing the whole message column into horizontal scroll.
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

// A collapsed block shows only its header, like any other tool call. With expandBash it still
// shows the command, clipped to its first lines, for reading a session by what it ran;
// expanding shows all of it.
const BASH_PREVIEW_LINES = 6;

const NO_TIMES: ReadonlyMap<string, ToolCallTime> = new Map();

function isHung(block: ChatBlock, hung: ReadonlySet<string>): boolean {
  return block.kind === 'tool_use' && block.tool_use_id !== null && hung.has(block.tool_use_id);
}

function showsBashWhileCollapsed(block: ChatBlock, expandBash: boolean): boolean {
  return expandBash && bashInput(block) !== null;
}

function BashCommand({ command, full }: { command: string; full: boolean }) {
  const lines = command.split('\n');
  const hidden = full ? 0 : Math.max(0, lines.length - BASH_PREVIEW_LINES);
  const shown = hidden ? lines.slice(0, BASH_PREVIEW_LINES).join('\n') : command;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <pre
        style={{
          margin: 0,
          padding: '6px 8px',
          fontSize: 12,
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
          background: tokens.color.shellBackground,
          border: `1px solid ${tokens.color.border}`,
          borderLeft: `3px solid ${tokens.color.shellPrompt}`,
          borderRadius: 4,
          color: tokens.color.text,
        }}
      >
        {/* The prompt marks it as a shell command; user-select keeps it out of a copied command. */}
        <span style={{ color: tokens.color.shellPrompt, userSelect: 'none' }}>$ </span>
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

// A hung tool call's time: counting up while it runs, with no new transcript data needed, then
// its total from the call's transcript timestamp to its result's. Ticks in tenths while the
// display shows tenths, then once a second; only this span re-renders on a tick.
function CallDuration({ timing }: { timing: ToolCallTime }) {
  const { start, end } = timing;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (end !== null || Number.isNaN(start)) return;
    const timer = setTimeout(() => setNow(Date.now()), now - start < 10_000 ? 100 : 1000);
    return () => clearTimeout(timer);
  }, [start, end, now]);
  if (Number.isNaN(start) || (end !== null && Number.isNaN(end))) return null;
  const running = end === null;
  return (
    <span
      title={running ? 'Running for' : 'Took'}
      style={{
        flexShrink: 0,
        fontVariantNumeric: 'tabular-nums',
        color: running ? tokens.color.due : tokens.color.textMuted,
      }}
    >
      {formatCallDuration((end ?? now) - start)}
    </span>
  );
}

// lead and trail are the message's own header (role; timestamp and Copy), carried on the first
// block's toggle line so a message spends no line on a header of its own.
function BlockRow({
  addressed,
  collapsed,
  onToggle,
  showTags,
  expandBash,
  lead,
  trail,
  timing,
}: {
  addressed: AddressedBlock;
  collapsed: boolean;
  onToggle: () => void;
  showTags: boolean;
  expandBash: boolean;
  lead?: ReactNode;
  trail?: ReactNode;
  // Present for a tool call that hung: its header shows how long it has run, or took.
  timing?: ToolCallTime;
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, fontSize: 12 }}>
        {lead}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={`Toggle ${summary} block ${addressed.id}`}
          style={{
            flexShrink: 0,
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
        {timing && <CallDuration timing={timing} />}
        <span
          title={bash?.description ?? undefined}
          style={{
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: tokens.color.textMuted,
          }}
        >
          {bash?.description}
        </span>
        {trail}
      </div>
      {bash && (!collapsed || showsBashWhileCollapsed(block, expandBash)) && (
        <BashCommand command={bash.command} full={!collapsed} />
      )}
      {!collapsed && (
        <>
          {block.kind === 'text' && <Markdown text={block.text ?? ''} />}
          {block.kind === 'thinking' && <Markdown text={block.text ?? ''} color={tokens.color.thinking} />}
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
          {showTags && <TagList tags={addressed.tags} />}
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
// row's props (its entry, the collapse callbacks) are unchanged by an append, so
// React skips it and leaves its DOM, and any text selection inside it, untouched.
const MessageRow = memo(function MessageRow({
  entry,
  isCollapsed,
  onToggle,
  showTags,
  expandBash,
  openCalls,
  running,
  hungDone,
  hungTimes,
}: {
  entry: TranscriptEntry;
  showTags: boolean;
  expandBash: boolean;
  // Ids of the tool calls that start expanded for having hung (see SessionTranscript);
  // NONE_HUNG for a row with none, so a change in which calls hang re-renders only the rows
  // holding them.
  openCalls: ReadonlySet<string>;
  // A hung call in this row is still pending: the card takes the running background.
  running: boolean;
  // A call in this row hung and has finished: the card keeps a faint trace of the running tint.
  hungDone: boolean;
  // Times of the calls in this row that have hung; NO_TIMES for a row with none.
  hungTimes: ReadonlyMap<string, ToolCallTime>;
  isCollapsed: (block: AddressedBlock, hung: boolean) => boolean;
  onToggle: (block: AddressedBlock, hung: boolean) => void;
}) {
  const { message } = entry;
  const addressedBlocks = entry.blocks;
  if (addressedBlocks.length === 0) return null;
  const isUser = message.role === 'user';
  const isHuman = isUser && isHumanText(message);
  const isFinal = !isUser && isTurnFinal(message);
  return (
    <div
      aria-busy={running}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${tokens.color.border}`,
        background: running
          ? tokens.color.runningCall
          : hungDone
            ? tokens.color.hungCallDone
            : isFinal
              ? tokens.color.turnFinal
              : isHuman
                ? tokens.color.humanMessage
                : isUser
                  ? tokens.color.surface
                  : 'transparent',
      }}
    >
      {addressedBlocks.map((addressed, i) => (
        <BlockRow
          key={addressed.id}
          addressed={addressed}
          collapsed={isCollapsed(addressed, isHung(addressed.block, openCalls))}
          onToggle={() => onToggle(addressed, isHung(addressed.block, openCalls))}
          showTags={showTags}
          expandBash={expandBash}
          timing={
            addressed.block.kind === 'tool_use' && addressed.block.tool_use_id !== null
              ? hungTimes.get(addressed.block.tool_use_id)
              : undefined
          }
          lead={
            i === 0 && (
              <span style={{ flexShrink: 0, fontWeight: 600, color: isUser ? tokens.color.accent : tokens.color.text }}>
                {message.role}
              </span>
            )
          }
          trail={
            i === 0 && (
              <div
                style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8, color: tokens.color.textMuted }}
              >
                <span>{message.timestamp}</span>
                <CopyMarkdownButton getText={() => messageToMarkdown(message, addressedBlocks)} />
              </div>
            )
          }
        />
      ))}
    </div>
  );
});

// The assistant's last message of a turn, after which it stops and waits for a reply (from a
// person, or from an agent or background task). Claude Code writes each content block of a
// message as its own transcript line, and every line carries the whole message's stop_reason,
// so each card of a final message (its thinking and its text) is marked. Only end_turn counts:
// tool_use leads into a tool call; stop_sequence and refusal occur on the harness's synthetic
// API-error messages, which are errors rather than replies; max_tokens is a reply cut off, not
// finished; and lines with no stop_reason come
// from messages the harness never finished writing.
function isTurnFinal(message: ChatMessage): boolean {
  return message.blocks.some((b) => b.tags.stop_reason === 'end_turn');
}

// Text a person typed, as opposed to a tool result or text the harness injected (isMeta) on the user's turn.
function isHumanText(message: ChatMessage): boolean {
  return message.blocks.some((b) => b.kind === 'text' && b.tags.isMeta !== 'true');
}

// A card folds into a run when every block it shows starts collapsed, so by default it shows
// nothing but headers. The default, not the current state, decides: expanding one card inside
// an open run leaves the run whole. A Bash call never folds with expandBash, since then its command
// shows while collapsed. A card with no blocks shows nothing and does not break a run. A stretch shorter than minRun cards stays as is.

type Segment = { kind: 'entry'; index: number } | { kind: 'run'; start: number; indices: number[] };

function segmentEntries(
  entries: TranscriptEntry[],
  showThinking: boolean,
  expandBash: boolean,
  openCalls: ReadonlySet<string>,
  minRun: number,
): Segment[] {
  const segments: Segment[] = [];
  let run: number[] = [];
  const flush = () => {
    if (run.length >= minRun) segments.push({ kind: 'run', start: run[0], indices: run });
    else segments.push(...run.map((index): Segment => ({ kind: 'entry', index })));
    run = [];
  };
  entries.forEach((entry, index) => {
    const shown = entry.blocks;
    if (shown.length === 0) return;
    const foldable = (a: AddressedBlock) =>
      defaultCollapsed(a, showThinking, isHung(a.block, openCalls)) && !showsBashWhileCollapsed(a.block, expandBash);
    if (shown.every(foldable)) run.push(index);
    else {
      flush();
      segments.push({ kind: 'entry', index });
    }
  });
  flush();
  return segments;
}

const runToggleStyle = {
  alignSelf: 'flex-start',
  padding: '4px 10px',
  border: `1px dashed ${tokens.color.border}`,
  borderRadius: 8,
  background: 'transparent',
  color: tokens.color.textMuted,
  fontSize: 12,
  cursor: 'pointer',
} as const;

// The bar form of a run toggle: a full-width rule like <hr>. Its padding is the hit area, so
// the thin line stays easy to click, and the negative margin cancels that padding so the bar
// adds no height beyond the list's own gap.
const runBarStyle = {
  display: 'block',
  width: '100%',
  padding: '4px 0',
  margin: '-4px 0',
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
} as const;

// Distance from the bottom, in pixels, within which the message pane counts as scrolled to
// the bottom and keeps following new messages.
const FOLLOW_THRESHOLD_PX = 40;

interface SessionTranscriptProps {
  sessionId: string;
  // Open at the newest message and follow, for a live session; otherwise open at the top.
  startAtBottom?: boolean;
}

// The raw Claude Code JSONL transcript for one session -- every user/assistant message,
// tool_use/tool_result block. Distinct from a Channel DM
// (frontend/src/channels/): this reads the session's own transcript file, not the
// cross-session ChannelMessage mailbox -- see the two-tab split in AgentPage.tsx for why they
// must never be conflated into one view. A live session's new messages are appended at the
// bottom as they are written (see useSessionChat); while the message pane is scrolled to the
// bottom it follows them.
export default function SessionTranscript({ sessionId, startAtBottom = false }: SessionTranscriptProps) {
  const { showTags, showThinking, collapsedAsBars, barColor, expandBash, hungCallSeconds, keepHungCallsOpen } =
    useTranscriptSettings();
  const [intervalSeconds] = useRefreshIntervalSetting();
  const { entries, loading, error } = useSessionChat(sessionId, intervalSeconds);
  const { isCollapsed, toggle } = useCollapseState(showThinking);
  const times = useMemo(() => toolCallTimes(entries), [entries]);
  const hung = useHungToolCalls(times, hungCallSeconds);
  // Only calls that hung show a time: a call that never hung stays out of the way, timing and all.
  const hungTimes = useMemo(() => new Map([...times].filter(([id]) => hung.all.has(id))), [hung.all, times]);
  // A hung call starts expanded while it runs; with keepHungCallsOpen it stays expanded after it
  // finishes, so what it did remains in view, and its tint fades from runningCall to hungCallDone.
  const openCalls = keepHungCallsOpen ? hung.all : hung.running;
  const segments = useMemo(
    () => segmentEntries(entries, showThinking, expandBash, openCalls, collapsedAsBars ? 1 : 2),
    [entries, showThinking, expandBash, openCalls, collapsedAsBars],
  );
  // Runs the user opened, by the index of their first entry: stable while a live transcript
  // appends, since new entries only extend the last run.
  const [openRuns, setOpenRuns] = useState<Set<number>>(new Set());
  const toggleRun = useCallback((start: number) => {
    stopFollowing();
    setOpenRuns((prev) => {
      const next = new Set(prev);
      if (!next.delete(start)) next.add(start);
      return next;
    });
  }, []);

  // Whether the pane was at the bottom before the latest render, updated on every scroll.
  // Read in the layout effect below, after new rows are in the DOM but before paint, so a
  // follow scroll never shows a frame of the old position.
  const paneRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(false);
  const seenCountRef = useRef(0);
  // Opening or closing a card means reading, not following: without this, a card expanded at the
  // bottom would grow the content and the follow pin would scroll its start out of view.
  // Scrolling back to the bottom resumes following.
  function stopFollowing() {
    followRef.current = false;
  }
  const toggleCard = useCallback(
    (block: AddressedBlock, blockHung: boolean) => {
      stopFollowing();
      toggle(block, blockHung);
    },
    [toggle],
  );
  const onPaneScroll = useCallback(() => {
    const pane = paneRef.current;
    if (pane) followRef.current = pane.scrollHeight - pane.scrollTop - pane.clientHeight <= FOLLOW_THRESHOLD_PX;
  }, []);
  // Whether the first load has been positioned yet: at the top, or with startAtBottom at the
  // bottom and following. startAtBottom can arrive after the first entries do.
  const placedRef = useRef(false);
  useLayoutEffect(() => {
    const previousCount = seenCountRef.current;
    seenCountRef.current = entries.length;
    const pane = paneRef.current;
    if (!pane || entries.length === 0) return;
    if (!placedRef.current) {
      if (startAtBottom) {
        pane.scrollTop = pane.scrollHeight;
        followRef.current = true;
        placedRef.current = true;
      }
      if (previousCount === 0) return;
    }
    if (entries.length > previousCount && followRef.current) pane.scrollTop = pane.scrollHeight;
  }, [entries, startAtBottom]);
  // Neither a pane that shrinks (under a growing message composer) nor content that grows after
  // it is laid out (markdown and fonts finishing after the first scroll to the bottom) fires a
  // scroll event, and either would leave the newest message partly out of view; keep it pinned.
  const contentRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const pane = paneRef.current;
    const content = contentRef.current;
    if (!pane || !content) return;
    const observer = new ResizeObserver(() => {
      if (followRef.current) pane.scrollTop = pane.scrollHeight;
    });
    observer.observe(pane);
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, flex: 1 }}>
      {loading && <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>Loading...</p>}
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && entries.length === 0 && (
        <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>No chat messages found.</p>
      )}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div ref={paneRef} onScroll={onPaneScroll} style={{ flex: 1, minWidth: 0, height: '100%', overflowY: 'auto' }}>
          <div ref={contentRef} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {segments.map((segment) => {
              const row = (i: number) => (
                <MessageRow
                  key={i}
                  entry={entries[i]}
                  isCollapsed={isCollapsed}
                  onToggle={toggleCard}
                  showTags={showTags}
                  expandBash={expandBash}
                  openCalls={entries[i].blocks.some((a) => isHung(a.block, openCalls)) ? openCalls : NONE_HUNG}
                  running={entries[i].blocks.some((a) => isHung(a.block, hung.running))}
                  hungDone={entries[i].blocks.some((a) => isHung(a.block, hung.finished))}
                  hungTimes={entries[i].blocks.some((a) => isHung(a.block, hung.all)) ? hungTimes : NO_TIMES}
                />
              );
              if (segment.kind === 'entry') return row(segment.index);
              const open = openRuns.has(segment.start);
              return (
                <div key={`run-${segment.start}`} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {collapsedAsBars ? (
                    <RunBar
                      count={segment.indices.length}
                      open={open}
                      color={barColor}
                      onToggle={() => toggleRun(segment.start)}
                    />
                  ) : (
                    <button type="button" onClick={() => toggleRun(segment.start)} style={runToggleStyle}>
                      {open ? '▾' : '▸'} {segment.indices.length} collapsed cards
                    </button>
                  )}
                  {open && segment.indices.map(row)}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function RunBar({
  count,
  open,
  color,
  onToggle,
}: {
  count: number;
  open: boolean;
  color: string;
  onToggle: () => void;
}) {
  const label = `${open ? 'Hide' : 'Show'} ${count} collapsed card${count === 1 ? '' : 's'}`;
  return (
    <button type="button" onClick={onToggle} aria-expanded={open} aria-label={label} title={label} style={runBarStyle}>
      <span style={{ display: 'block', height: 2, background: color, opacity: open ? 1 : 0.6 }} />
    </button>
  );
}
