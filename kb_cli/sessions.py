"""Live harness-session discovery and cross-session messaging (see kb Goal #46), plus the
original Claude Code CLI transcript listing this module used to be limited to (now under
`kb sessions history` / `kb sessions list --all`).

`kb sessions` (bare, or `list`) shows only currently-live sessions -- registered via
HarnessSession.register (called from a SessionStart hook) and filtered to pid-alive rows, not
parsed from *.jsonl transcripts. That parsing still exists, moved to `history`, for browsing
past sessions by title/timestamp the way this module always did.

Every message lives in a Channel (models.py) -- a DM is a nameless two-subscriber channel
(Channel.find_or_create_dm), broadcast is the channel named "broadcast" every session
auto-subscribes to at registration. See Note #157 for why FileChanged (a filesystem-watch
hook) doesn't give true idle-session async delivery in Claude Code, and Goal #46 for the
resulting two-layer delivery design this module's `inbox` (checked from UserPromptSubmit) and
`listen` (an optional foreground poll loop) implement.
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple, Optional, Sequence

import psutil
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from harness import current_session_id, find_session_transcript_path, session_transcript_title
from models import Channel, ChannelMessage, ChannelRead, ChannelSubscription, HarnessSession

from kb_cli._util import print_table, resolve_text_arg

_PROJECTS_DIR = Path.home() / ".claude" / "projects"

_BROADCAST_CHANNEL_NAME = "broadcast"

_LISTEN_POLL_SECONDS = 5

# How many characters of a message body to preview in `kb sessions listen`'s own printed
# output -- long enough to judge relevance/urgency at a glance, short enough that a large
# message doesn't derail whatever the agent was already doing (see kb Note #159's follow-up:
# the completion notification's own <summary> line never carries message content, only a
# pointer to the output file, so this preview is what actually needs to be self-sufficient).
_LISTEN_PREVIEW_CHARS = 200


def _humanize_age(delta_seconds: float) -> str:
    """Renders a duration as e.g. "3m", "2h", "5d" -- coarsest unit that keeps at least one
    significant digit, matching age_marker's own d/w granularity style (base.py) but finer
    since session ages/message gaps are commonly under a day, unlike record age."""
    seconds = int(delta_seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def _last_message_at(session: Session, session_id: str) -> Optional[datetime]:
    """Most recent ChannelMessage either sent by session_id or posted into any channel it
    subscribes to -- covers both directions (something it said, something it was told)
    rather than only inbound mail, since "time since most recent message" should reflect
    the session's own last activity in a channel either way."""
    channel_ids = session.scalars(
        select(ChannelSubscription.channel_id).where(ChannelSubscription.session_id == session_id)
    ).all()
    if not channel_ids:
        return None
    return session.scalar(select(func.max(ChannelMessage.created_at)).where(ChannelMessage.channel_id.in_(channel_ids)))


def _session_info(path: Path) -> dict[str, str] | None:
    """Return {'title', 'timestamp'} for a session transcript, or None if empty/unreadable.
    Title resolution itself lives in harness.session_transcript_title (shared with the web
    UI's channels_router, which refreshes HarnessSession.title from the same transcripts) --
    this wrapper adds only the last-activity timestamp, which that shared function doesn't
    need for its own callers."""
    last_ts = None
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = d.get("timestamp")
            if ts:
                last_ts = ts

    resolved_title = session_transcript_title(path)
    if resolved_title is None or last_ts is None:
        return None
    return {"title": resolved_title, "timestamp": last_ts}


def _require_session_id() -> str:
    session_id = current_session_id()
    if not session_id:
        print("kb sessions: no harness session ID detected (current_session_id() returned None)")
        raise SystemExit(1)
    return session_id


def _find_claude_ancestor_pid() -> int:
    """Walk up the process tree from this (short-lived `kb` subprocess') pid to find the
    nearest ancestor whose command name is `claude` -- neither os.getpid() (this process)
    nor os.getppid() (its immediate parent, typically an intermediate shell the hook was
    invoked through) is the actual long-lived harness process whose liveness matters for
    HarnessSession.is_alive(). Falls back to os.getppid() if no `claude` ancestor is found
    (e.g. running kb sessions register manually, outside any real hook), or if psutil can't
    read the tree (process exited mid-walk, permissions)."""
    try:
        proc: Optional[psutil.Process] = psutil.Process(os.getpid())
        for _ in range(20):
            if proc is None:
                break
            proc = proc.parent()
            if proc is not None and proc.name() == "claude":
                return proc.pid
    except psutil.Error:
        pass
    return os.getppid()


def cmd_register(args: argparse.Namespace) -> None:
    """Called from a SessionStart hook -- session id read from stdin if piped (matches
    kb hooks daily-check's convention), falling back to current_session_id() for manual
    testing. Reads cwd from the OS directly (a SessionStart hook's own cwd) and pid via
    _find_claude_ancestor_pid(), since the calling `kb` process is a short-lived
    grandchild of the actual long-lived `claude` process, not that process itself."""
    session_id = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    if not session_id:
        session_id = current_session_id() or ""
    if not session_id:
        return
    HarnessSession.register(
        args.session, session_id, cwd=os.getcwd(), pid=_find_claude_ancestor_pid(), title=args.title
    )
    broadcast = Channel.get_or_create_named(args.session, _BROADCAST_CHANNEL_NAME)
    ChannelSubscription.subscribe(args.session, channel_id=broadcast.id, session_id=session_id)
    args.session.commit()


def refresh_agent_title(agent: HarnessSession) -> None:
    """Pull the current title (custom-title event, else ai-title, else first user message --
    same resolution Claude Code's own session picker uses) from the agent's own transcript
    and write it onto HarnessSession.title if it changed. HarnessSession.title is only ever
    set once, at SessionStart (kb sessions register), so a mid-session /rename never reaches
    it on its own -- this keeps it current on every live-session read rather than adding a
    second write path for the CLI-side rename event, since a transcript read is cheap and both
    `kb sessions list` and the frontend's session listings read every live agent's identity
    per call anyway."""
    path = find_session_transcript_path(agent.id)
    if path is None:
        return
    title = session_transcript_title(path)
    if title is not None and title != agent.title:
        agent.title = title


class LiveSessionInfo(NamedTuple):
    """One row of `kb sessions list`'s live-session view, independent of how it's rendered --
    shared by the CLI table and the frontend's JSON API (api/sessions_router.py) so the two
    surfaces can never drift on what "listening"/"age"/"last message" mean."""

    id: str
    is_self: bool
    status: str
    listening: str  # "", "stale", or "yes (pid N)"
    age_seconds: float
    last_message_seconds: Optional[float]
    cwd: str
    title: str


def list_live_sessions(session: Session) -> tuple[list[LiveSessionInfo], int]:
    """Clears stale listener flags as a side effect (matching `kb sessions list`'s prior
    behavior) and returns (one LiveSessionInfo per currently-live session, count cleared)."""
    cleared = HarnessSession.clear_stale_listeners(session)
    live = HarnessSession.live(session)
    self_id = current_session_id()
    now = datetime.now(timezone.utc)
    infos = []
    for row in live:
        refresh_agent_title(row)
        if row.is_listening_live():
            listening = f"yes (pid {row.listener_pid})"
        elif row.is_listening:
            # Flag still true but listener_pid doesn't resolve -- a dead listener that never
            # cleared its own flag (SIGKILL/OOM/harness reap, see HarnessSession's docstring),
            # not a live one. Surfaced as "stale" rather than blank "no" so this is diagnosable
            # at a glance instead of looking identical to a session that was never listening --
            # `kb sessions listen` self-heals it on next start, this is a status readout only.
            listening = "stale"
        else:
            listening = ""
        # created_at is set once at first registration (HarnessSession.register upserts, never
        # re-inserts on a resumed/restarted `kb sessions listen`), so this is genuinely "when
        # the session was created," not reset by listen's own exit-and-restart cycle.
        age_seconds = (now - row.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        last_msg_at = _last_message_at(session, row.id)
        last_message_seconds = (
            (now - last_msg_at.replace(tzinfo=timezone.utc)).total_seconds() if last_msg_at is not None else None
        )
        infos.append(
            LiveSessionInfo(
                id=row.id,
                is_self=row.id == self_id,
                status=row.status.value,
                listening=listening,
                age_seconds=age_seconds,
                last_message_seconds=last_message_seconds,
                cwd=row.cwd,
                title=row.title or "",
            )
        )
    return infos, len(cleared)


def cmd_list(args: argparse.Namespace) -> None:
    if args.all:
        cmd_history(args)
        return
    infos, cleared_count = list_live_sessions(args.session)
    args.session.commit()  # persists clear_stale_listeners' cleanup
    if cleared_count:
        print(
            f"(cleared {cleared_count} stale listener flag{'s' if cleared_count != 1 else ''} -- "
            f"dead process{'es' if cleared_count != 1 else ''}, DB bookkeeping only, "
            "see `kb sessions cleanup --help`)"
        )
    if not infos:
        print("No live sessions.")
        return
    headers = ["Session", "You?", "Status", "Listening", "Age", "Last Msg", "Cwd", "Title"]
    rows = [
        [
            # Full id, not truncated -- kb sessions send needs to copy-paste this
            # directly, and a shortened id here is a broken id there.
            info.id,
            "yes" if info.is_self else "",
            info.status,
            info.listening,
            _humanize_age(info.age_seconds),
            _humanize_age(info.last_message_seconds) if info.last_message_seconds is not None else "",
            info.cwd,
            info.title,
        ]
        for info in infos
    ]
    print_table(headers, rows)


def cmd_history(args: argparse.Namespace) -> None:
    if not _PROJECTS_DIR.is_dir():
        print(f"No sessions directory found at {_PROJECTS_DIR}")
        return

    sessions = []
    for project_dir in _PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_path in project_dir.glob("*.jsonl"):
            info = _session_info(jsonl_path)
            if info:
                sessions.append({"project": project_dir.name, **info})

    if not sessions:
        print("No sessions found.")
        return

    sessions.sort(key=lambda s: s["timestamp"], reverse=True)

    counts: dict[str, int] = {}
    for s in sessions:
        counts[s["project"]] = counts.get(s["project"], 0) + 1

    print("Directories:")
    for project, count in sorted(counts.items(), key=lambda kv: kv[0]):
        print(f"  {project}  ({count} session{'s' if count != 1 else ''})")
    print()

    headers = ["Date", "Directory", "Title"]
    rows = [[s["timestamp"][:16].replace("T", " "), s["project"], s["title"]] for s in sessions]
    print_table(headers, rows)


class ChatBlock(NamedTuple):
    """One piece of a chat message's content -- a text block, a tool call, or a tool
    result -- kept separate from ChatMessage since a single message commonly carries several
    (e.g. one assistant turn with a text block followed by a tool_use block).

    `kind` is the most specific shape this parser recognizes today ("text", "tool_use",
    "tool_result", or "unknown" for a future content-block type it doesn't -- see
    _extract_blocks). `tags` is deliberately open-ended metadata about this block and its
    parent message (every scalar field the raw JSONL carries, flattened -- see
    _flatten_tags) -- the frontend legend/filter panel is built entirely from whatever keys
    and values actually occur in `tags` across a session, so a new Claude Code JSONL field
    (a new `stop_reason`, a new hook type, a future MCP server) becomes filterable the moment
    it appears in a transcript, with no parser change required."""

    kind: str  # "text", "tool_use", "tool_result", or "unknown"
    text: Optional[str] = None  # for kind == "text"
    tool_name: Optional[str] = None  # for kind == "tool_use"
    tool_input: Optional[dict[str, Any]] = None  # for kind == "tool_use"
    tool_output: Optional[str] = None  # for kind == "tool_result"
    is_error: bool = False  # for kind == "tool_result"
    tags: dict[str, str] = {}


class ChatMessage(NamedTuple):
    """One line of real chat content from a session transcript -- a `type: "user"` or
    `type: "assistant"` JSONL record, in file order. Every other JSONL line (hook output,
    tool-listing deltas, mode/permission-mode bookkeeping) is not a message and is dropped
    entirely, not summarized -- this is the same content a viewer scrolling the raw
    transcript would call "the conversation," nothing added or condensed."""

    role: str  # "user" or "assistant"
    timestamp: str
    blocks: list[ChatBlock]


# Keys whose value is either the large content this parser already surfaces structurally
# (message.content itself, a tool_result's content, a tool_use's input) or pure recursion
# plumbing -- flattening into these would either duplicate `text`/`tool_output`/`tool_input`
# as noisy tags or blow up into hundreds of near-unique per-message keys (uuid, requestId)
# that would never usefully group two blocks together in a filter panel.
_TAG_EXCLUDE_KEYS = frozenset(
    {
        "content",
        "input",
        "message",
        "uuid",
        "parentUuid",
        "sourceToolAssistantUUID",
        "requestId",
        "id",
        "tool_use_id",
        "toolUseID",
        "sessionId",
        "session_id",
        "promptId",
        "type",  # already exposed unambiguously as ChatBlock.kind; raw JSONL overloads
        # this key at both message level ("user"/"assistant") and block level
        # ("text"/"tool_use"/...), so flattening it verbatim would silently let one
        # overwrite the other in the merged tag map.
        "usage",  # per-call token accounting -- effectively unique per message, never a
        # useful group-by facet, and large enough (a dozen+ nested numbers) to drown out
        # the tags that are.
        "toolUseResult",  # duplicates bulk tool output already surfaced as tool_output.
        "stdout",
        "stderr",
    }
)


def _flatten_tags(obj: object, prefix: str = "") -> dict[str, str]:
    """Recursively collects every scalar (str/bool/int/float) leaf in obj into a flat
    {dotted.path: str(value)} map -- the generic enrichment this whole module's tags-based
    filtering rests on. Deliberately has no notion of which fields are "interesting"; that
    judgment is left entirely to the frontend legend, which only ever shows keys/values that
    actually occurred. See _TAG_EXCLUDE_KEYS for the few keys skipped to keep this from
    surfacing bulk content or single-use identifiers as if they were filterable facets."""
    tags: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            # Excluded only at this call's own top level (prefix == ""), not by bare key
            # name at any depth -- a nested field that happens to share a name with an
            # excluded top-level key (e.g. caller.type vs. the message/block-level `type`
            # this module overloads) is a distinct, real facet and must survive.
            if not prefix and key in _TAG_EXCLUDE_KEYS:
                continue
            child_prefix = f"{prefix}.{key}" if prefix else key
            tags.update(_flatten_tags(value, child_prefix))
    elif isinstance(obj, list):
        # Lists of dicts (e.g. multiple attachments) aren't indexed into the key path --
        # a list is walked for its scalar/dict members but never appears as its own tag,
        # since "index 2 of some list" is not a meaningful filter facet.
        for item in obj:
            tags.update(_flatten_tags(item, prefix))
    elif isinstance(obj, bool):
        if prefix:
            tags[prefix] = "true" if obj else "false"
    elif isinstance(obj, (str, int, float)):
        if prefix and obj != "":
            tags[prefix] = str(obj)
    return tags


def _extract_blocks(content: object, message_tags: dict[str, str]) -> list[ChatBlock]:
    """Parses message.content into ChatBlocks as specifically as this function recognizes
    (text/tool_use/tool_result), falling back to kind="unknown" with the block's own raw
    scalar fields flattened into tags for anything else -- a future content-block type this
    parser has never seen renders as a generic block instead of being silently dropped."""
    if isinstance(content, str):
        return [ChatBlock(kind="text", text=content, tags=message_tags)] if content else []
    if not isinstance(content, list):
        return []
    blocks = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        block_tags = {**message_tags, **_flatten_tags(item)}
        if item_type == "text":
            blocks.append(ChatBlock(kind="text", text=item.get("text", ""), tags=block_tags))
        elif item_type == "tool_use":
            tool_name = item.get("name")
            if isinstance(tool_name, str) and tool_name.startswith("mcp__"):
                # mcp__<server>__<tool> is Claude Code's own naming convention for every MCP
                # tool -- splitting it out gives the legend an "MCP server"/"MCP tool" facet
                # without hardcoding which servers/tools exist.
                parts = tool_name.split("__", 2)
                if len(parts) == 3:
                    block_tags = {**block_tags, "mcp.server": parts[1], "mcp.tool": parts[2]}
            blocks.append(
                ChatBlock(kind="tool_use", tool_name=tool_name, tool_input=item.get("input"), tags=block_tags)
            )
        elif item_type == "tool_result":
            result_content = item.get("content")
            if isinstance(result_content, list):
                result_text = "\n".join(
                    c.get("text", "") for c in result_content if isinstance(c, dict) and c.get("type") == "text"
                )
            else:
                result_text = str(result_content) if result_content is not None else ""
            blocks.append(
                ChatBlock(
                    kind="tool_result", tool_output=result_text, is_error=bool(item.get("is_error")), tags=block_tags
                )
            )
        else:
            blocks.append(ChatBlock(kind="unknown", tags=block_tags))
    return blocks


def list_chat_messages(path: Path) -> list[ChatMessage]:
    """Every real chat message in a session transcript, in file order, with nothing
    compacted or summarized -- backs both a future `kb sessions show --chat` and the
    frontend's session-viewer page. See ChatMessage's own docstring for what counts as
    a message versus dropped bookkeeping, and ChatBlock's for the generic tags this attaches
    to every block for frontend-driven filtering."""
    messages = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") not in ("user", "assistant"):
                continue
            message = d.get("message")
            if not isinstance(message, dict):
                continue
            # Flattened once per line (top-level record fields like isSidechain/stop_reason/
            # effort/model/origin/promptSource, plus message's own non-content fields like
            # role/model/usage) and inherited by every block on that line -- these describe
            # the whole message, not any one block, so every block should carry them as tags.
            message_tags = {**_flatten_tags(d), **_flatten_tags(message)}
            blocks = _extract_blocks(message.get("content"), message_tags)
            if not blocks:
                continue
            messages.append(
                ChatMessage(role=message.get("role", d["type"]), timestamp=d.get("timestamp", ""), blocks=blocks)
            )
    return messages


def cmd_show(args: argparse.Namespace) -> None:
    path = find_session_transcript_path(args.session_id)
    if path is None:
        if not args.title:
            print(f"No session found with id {args.session_id}")
        return

    info = _session_info(path)
    if info is None:
        return

    if args.title:
        print(info["title"])
        return

    print(f"Project: {path.parent.name}")
    print(f"Title:   {info['title']}")
    print(f"Updated: {info['timestamp']}")


def cmd_send(args: argparse.Namespace) -> None:
    """Sending to a no-longer-live recipient is deliberately not blocked -- to_session is a
    real FK against HarnessSession (a row must exist, and does persist after the process
    behind it exits), so the mailbox model doesn't require the recipient to be currently
    running -- but the sending session should never be left assuming a reply is coming from
    a session that will in practice never read it. The user's own stated workflow (kb Goal #46
    design discussion, 2026-08-17): a session gets closed specifically when there's no intent
    to return to it, so a message to a dead session should read as a prompt to go investigate
    the question directly instead of waiting on that session to answer. A truly unregistered
    session id (no HarnessSession row at all, e.g. a typo) is refused outright -- that's not
    "will never read it," it's "this id was never a real session.\" """
    from_session = _require_session_id()
    recipient = args.session.get(HarnessSession, args.to)
    if recipient is None:
        print(f"kb sessions send: {args.to!r} is not a known session id (see `kb sessions list`)")
        raise SystemExit(1)
    channel = Channel.find_or_create_dm(args.session, from_session, args.to)
    msg = ChannelMessage.post(
        args.session, channel_id=channel.id, from_session=from_session, body=resolve_text_arg(args.body)
    )
    args.session.commit()
    print(f"<ChannelMessage #{msg.id} {from_session}->{args.to}>")

    if not recipient.is_alive():
        print(
            f"Note: session {args.to} is not currently running -- it will likely never read this message unless "
            "resumed. Don't wait on a reply; investigate the question directly instead."
        )


def cmd_broadcast(args: argparse.Namespace) -> None:
    """Sends one message into the "broadcast" Channel, which every session auto-subscribes to
    at registration (cmd_register) -- one ChannelMessage row, not a fan-out into one row per
    recipient; who receives it is just whoever is subscribed and live, the same as any other
    channel. Recipients see it tagged [BROADCAST] in inbox/listen output (the reader side
    applies that tag from the channel's own name, not something baked into the stored body).

    --dry-run prints exactly who would receive it (the live, subscribed session list) without
    writing anything -- added after a live mistake where a broadcast meant as a test of the
    feature itself was sent for real and reached every other session unintentionally."""
    from_session = _require_session_id()
    broadcast = Channel.get_or_create_named(args.session, _BROADCAST_CHANNEL_NAME)
    subscriber_ids = set(
        args.session.scalars(
            select(ChannelSubscription.session_id).where(ChannelSubscription.channel_id == broadcast.id)
        ).all()
    )
    live = [row for row in HarnessSession.live(args.session) if row.id != from_session and row.id in subscriber_ids]
    if not live:
        print("kb sessions broadcast: no other live sessions to send to.")
        return
    body = resolve_text_arg(args.body)
    if args.dry_run:
        print(f"kb sessions broadcast --dry-run: would send to {len(live)} session(s), nothing sent:")
        for row in live:
            print(f"  {row.id}  ({row.cwd})")
        print(f"Body: {body}")
        return
    msg = ChannelMessage.post(args.session, channel_id=broadcast.id, from_session=from_session, body=body)
    args.session.commit()
    print(f"<ChannelMessage #{msg.id} {from_session}->[broadcast]>")
    print(f"Delivered to {len(live)} live session(s):")
    for row in live:
        print(f"  {row.id}  ({row.cwd})")


def _channel_tag(session: Session, channel_id: int) -> str:
    """[NAME] for a named channel (e.g. [BROADCAST]), blank for a DM (nameless channel) --
    generalizes what used to be a single is_broadcast boolean special case."""
    channel = session.get(Channel, channel_id)
    if channel is None or channel.name is None:
        return ""
    return f"[{channel.name.upper()}] "


def cmd_inbox(args: argparse.Namespace) -> None:
    """Called both by a person checking their own session's mail and by the
    UserPromptSubmit hook adapter (see kb Goal #46 Layer 1) -- unread messages are printed and
    a ChannelRead row is recorded per affected channel in the same call, matching this design's
    read-event-log state (no separate archive/dismiss step)."""
    to_session = _require_session_id()
    messages = (
        ChannelMessage.unread(args.session, to_session) if not args.all else _all_messages(args.session, to_session)
    )
    if not messages:
        if not args.quiet:
            print("No new messages.")
        return
    channel_ids = set()
    for msg in messages:
        tag = _channel_tag(args.session, msg.channel_id)
        print(f"From {msg.from_session} at {msg.created_at.isoformat()}:\n  {tag}{msg.body}\n")
        channel_ids.add(msg.channel_id)
    if not args.all:
        for channel_id in channel_ids:
            ChannelRead.record(args.session, channel_id=channel_id, session_id=to_session)
    args.session.commit()


def _all_messages(session: Session, to_session: str) -> Sequence[ChannelMessage]:
    """--all support: every message (read or not) in every channel to_session is subscribed
    to, newest-filtering-agnostic -- unlike ChannelMessage.unread this ignores read cursors
    entirely, matching the old --all's "show everything, mark nothing" behavior."""
    channel_ids = session.scalars(
        select(ChannelSubscription.channel_id).where(ChannelSubscription.session_id == to_session)
    ).all()
    if not channel_ids:
        return []
    return session.scalars(
        select(ChannelMessage)
        .where(ChannelMessage.channel_id.in_(channel_ids), ChannelMessage.from_session != to_session)
        .order_by(ChannelMessage.created_at)
    ).all()


def cmd_listen(args: argparse.Namespace) -> None:
    """Foreground poll loop -- meant to be launched via run_in_background (see kb Goal #46
    Layer 2), never run in the foreground of an interactive session. Polls this session's
    own inbox (always current_session_id(), never an argument -- see Goal #46's explicit
    decision against making the caller supply/copy a session id) and exits the moment new
    mail shows up, so its own background-task-completion notification is the delivery
    mechanism -- confirmed live during this feature's design to actually surface unprompted
    in an idle session. Sets is_listening while running and clears it on the way out
    (including on an unhandled exception), so a killed listener never leaves a stale
    "listening" status behind."""
    to_session = _require_session_id()
    # Sweep detached listeners (orphaned by a harness that exited without tearing down its
    # background `kb sessions listen` task -- e.g. /clear, terminal closed) before doing
    # anything else, so a fresh listener starting up is also the point that cleans up after
    # any it finds -- confirmed live 2026-08-17, two such orphans found via manual pgrep/ps
    # before this got automated. Runs for every session's rows, not just to_session's own, for
    # the same reason clear_stale_listeners() does -- see kb Note #159 and
    # HarnessSession.detached_listeners()'s docstring for why this is safe to do unscoped.
    killed = HarnessSession.kill_detached_listeners(args.session)
    if killed:
        args.session.commit()
        for row, pid in killed:
            print(f"kb sessions listen: cleaned up detached listener for session {row.id} (was pid {pid})")
    row = args.session.get(HarnessSession, to_session)
    if row is None:
        print(
            f"kb sessions listen: session {to_session} is not registered -- run `kb hooks session-register` "
            "once (covers a session that started before the SessionStart hook existed, or any other reason "
            "registration didn't happen), then retry"
        )
        raise SystemExit(1)
    if row.is_listening_live():
        # Refuse rather than try to kill the existing one -- a run_in_background shell is
        # entirely local to the harness session that started it, with no pid or handle
        # visible to this process, so there is no safe way to terminate it from here.
        # Two concurrent listeners for the same session would double-poll, race on
        # mark_read(), and stomp on is_listening in each other's `finally` block --
        # refusing to start a second one is the correct fix, not cross-process termination.
        # is_listening_live() (not the bare is_listening flag) is what makes this refusal
        # trustworthy -- a listener killed by SIGKILL/OOM/harness-reap without ever clearing
        # its own flag no longer wedges every future `kb sessions listen` for this session
        # (hit live, 2026-08-17, kb Note #163): the pid check below fails, so this branch is
        # skipped and a fresh listener starts normally instead of refusing forever.
        print(
            f"kb sessions listen: already listening for session {to_session} (per kb's own records) -- "
            "check your own harness's background-task list (not another kb command) for the existing one "
            "rather than starting a second listener for the same session."
        )
        raise SystemExit(1)
    if row.is_listening and not row.is_listening_live():
        # Flag was stuck true from a dead listener (see is_listening_live()'s docstring) --
        # self-heal it here rather than leaving the stale value in place until this row's own
        # finally block below overwrites it, so `kb sessions list`'s Listening column doesn't
        # keep reporting a dead listener as live in the window before this new one exits.
        row.is_listening = False
        row.listener_pid = None
        args.session.commit()

    def _handle_sigterm(signum: int, frame: object) -> None:
        # TaskStop (or any external kill -- including another session's `kb sessions listen`
        # startup sweep via kill_detached_listeners(), the common case: a harness that /clear'd
        # or exited left this listener attached to a now-superseded session id, and a newer
        # listener starting up for a different session reaped it) sends SIGTERM, not
        # KeyboardInterrupt -- without a handler that turns it into an exception, the `finally`
        # block below never runs and is_listening is left stuck True in the DB, forcing a manual
        # clear before the next `kb sessions listen` will start (hit live, 2026-08-17). SIGKILL
        # still can't be caught, same as any Unix process -- that gap is unavoidable, not fixed
        # here. Printing which session this was is what turns a bare, unexplained "exited with
        # code 143" in the harness's background-task list into something self-explanatory --
        # confirmed live 2026-08-18 that without this, a killed listener's own exit gives no clue
        # it was a routine cleanup rather than a crash.
        print(f"kb sessions listen: listener for session {to_session} is being cleaned up (SIGTERM, pid {os.getpid()})")
        sys.stdout.flush()
        raise SystemExit(143)  # 128 + SIGTERM, conventional exit code for a killed process

    signal.signal(signal.SIGTERM, _handle_sigterm)
    row.is_listening = True
    row.listener_pid = os.getpid()
    args.session.commit()
    print(f"kb sessions listen: listening for session {to_session} (pid {os.getpid()})")
    sys.stdout.flush()
    try:
        while True:
            messages = ChannelMessage.unread(args.session, to_session)
            if messages:
                # Deliberately not calling ChannelRead.record() here -- this print is a best-effort
                # preview whose actual delivery into the agent's context depends on the harness
                # notification firing and being read, neither of which listen can confirm. If it
                # recorded a read anyway, a failed/missed delivery would make `kb sessions inbox`
                # (the one deterministic fallback) come back empty too, hiding a message that was
                # never really seen (hit live, 2026-08-17 -- an agent explicitly ran `kb sessions
                # inbox` right after a listen completion and got "No new messages" because listen
                # had already marked it read). Recording a read only happens in cmd_inbox now, at
                # the point of actual confirmed consumption.
                for msg in messages:
                    tag = _channel_tag(args.session, msg.channel_id)
                    body = msg.body
                    if len(body) > _LISTEN_PREVIEW_CHARS:
                        preview = body[:_LISTEN_PREVIEW_CHARS] + "..."
                        print(
                            f"From {msg.from_session} at {msg.created_at.isoformat()} "
                            f"({len(body)} chars):\n  {tag}{preview}\n"
                            f"  (run `kb sessions inbox` to see the full message)\n"
                        )
                    else:
                        print(
                            f"From {msg.from_session} at {msg.created_at.isoformat()} "
                            f"({len(body)} chars):\n  {tag}{body}\n"
                        )
                # stdout is fully buffered (not line-buffered) once it's not a TTY, which is
                # always true for a run_in_background process -- an explicit flush here is
                # required so the printed message is actually visible in the captured output
                # before the process exits, rather than depending on Python's own exit-time
                # flush. See kb Note #159 for the bug this fixes and how it was verified.
                sys.stdout.flush()
                return
            time.sleep(_LISTEN_POLL_SECONDS)
    finally:
        row.is_listening = False
        row.listener_pid = None
        args.session.commit()


def cmd_cleanup(args: argparse.Namespace) -> None:
    """Explicit verb for the same DB-only stale-listener clear that `kb sessions list` already
    runs automatically -- for a script/hook that wants the clear without the rest of list's
    table output, or for running it on demand right after noticing a 'stale' row. Never touches
    an OS process (see HarnessSession.clear_stale_listeners docstring) -- this is always safe to
    run against every session's rows, not just your own, unlike killing a pid found via `ps aux`."""
    cleared = HarnessSession.clear_stale_listeners(args.session)
    args.session.commit()
    if not cleared:
        print("No stale listener flags found.")
        return
    for row in cleared:
        print(f"Cleared stale listener flag: session {row.id} (cwd={row.cwd!r})")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("sessions", help="Live harness sessions: discover, message, and listen")
    sub = parser.add_subparsers(dest="subcommand")

    list_parser = sub.add_parser("list", help="List currently-live sessions (default)")
    list_parser.add_argument(
        "--all", action="store_true", help="List all historical sessions instead (from *.jsonl transcripts)"
    )
    list_parser.set_defaults(func=cmd_list)

    history_parser = sub.add_parser(
        "history", help="List all historical sessions across all projects (*.jsonl transcripts)"
    )
    history_parser.set_defaults(func=cmd_history)

    show_parser = sub.add_parser("show", help="Show one historical session by its session_id")
    show_parser.add_argument("session_id", help="Session id (transcript filename stem)")
    show_parser.add_argument("--title", action="store_true", help="Print only the resolved title, no other output")
    show_parser.set_defaults(func=cmd_show)

    register_parser = sub.add_parser(
        "register", help="Register (or refresh) the current session as live -- called from a SessionStart hook"
    )
    register_parser.add_argument("--title", help="Session title, if already known")
    register_parser.set_defaults(func=cmd_register)

    send_parser = sub.add_parser("send", help="Send a message to another live session")
    send_parser.add_argument("to", help="Recipient's harness session id (see `kb sessions list`)")
    send_parser.add_argument("body", help="Message text, or - to read from stdin")
    send_parser.set_defaults(func=cmd_send)

    broadcast_parser = sub.add_parser(
        "broadcast", help="Send a message to every other live session (never to self), marked [BROADCAST]"
    )
    broadcast_parser.add_argument("body", help="Message text, or - to read from stdin")
    broadcast_parser.add_argument(
        "--dry-run", action="store_true", help="Print who would receive it without sending anything"
    )
    broadcast_parser.set_defaults(func=cmd_broadcast)

    inbox_parser = sub.add_parser("inbox", help="Show and mark-read this session's own new messages")
    inbox_parser.add_argument(
        "--all", action="store_true", help="Show every message, read or not, without marking anything read"
    )
    inbox_parser.add_argument("--quiet", action="store_true", help="Print nothing when there are no new messages")
    inbox_parser.set_defaults(func=cmd_inbox)

    cleanup_parser = sub.add_parser(
        "cleanup",
        help="Clear stale is_listening flags (dead listener processes) -- DB bookkeeping only, "
        "never touches an OS process. Also runs automatically as part of `kb sessions list`.",
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    listen_parser = sub.add_parser(
        "listen",
        help="Poll this session's own inbox in a loop, exiting the moment new mail arrives -- run via run_in_background",
    )
    listen_parser.set_defaults(func=cmd_listen)

    parser.set_defaults(func=cmd_list)
