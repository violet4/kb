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
from typing import Optional, Sequence

import psutil
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from harness import current_session_id
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
    """Return {'title', 'timestamp'} for a session transcript, or None if empty/unreadable."""
    title = None
    custom_title = None
    last_ts = None
    first_user_text = None
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
            t = d.get("type")
            if t == "ai-title":
                title = d.get("aiTitle")
            elif t == "custom-title":
                custom_title = d.get("customTitle")
            elif t == "user" and first_user_text is None and not d.get("isMeta"):
                content = d.get("message", {}).get("content")
                if isinstance(content, str):
                    first_user_text = content
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            first_user_text = c["text"]
                            break

    resolved_title = custom_title or title or first_user_text
    if resolved_title is None or last_ts is None:
        return None
    resolved_title = " ".join(resolved_title.split())
    if len(resolved_title) > 70:
        resolved_title = resolved_title[:67] + "..."
    return {"title": resolved_title, "timestamp": last_ts}


def _find_session_path(session_id: str) -> Path | None:
    """Locate a session transcript by its session_id (filename stem) across all projects."""
    if not _PROJECTS_DIR.is_dir():
        return None
    for project_dir in _PROJECTS_DIR.iterdir():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.is_file():
            return candidate
    return None


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


def cmd_list(args: argparse.Namespace) -> None:
    if args.all:
        cmd_history(args)
        return
    cleared = HarnessSession.clear_stale_listeners(args.session)
    if cleared:
        args.session.commit()
        print(
            f"(cleared {len(cleared)} stale listener flag{'s' if len(cleared) != 1 else ''} -- "
            f"dead process{'es' if len(cleared) != 1 else ''}, DB bookkeeping only, "
            "see `kb sessions cleanup --help`)"
        )
    live = HarnessSession.live(args.session)
    if not live:
        print("No live sessions.")
        return
    self_id = current_session_id()
    now = datetime.now(timezone.utc)
    headers = ["Session", "You?", "Status", "Listening", "Age", "Last Msg", "Cwd", "Title"]
    rows = []
    for row in live:
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
        age = _humanize_age((now - row.created_at.replace(tzinfo=timezone.utc)).total_seconds())
        last_msg_at = _last_message_at(args.session, row.id)
        last_msg = (
            _humanize_age((now - last_msg_at.replace(tzinfo=timezone.utc)).total_seconds())
            if last_msg_at is not None
            else ""
        )
        rows.append(
            [
                # Full id, not truncated -- kb sessions send needs to copy-paste this
                # directly, and a shortened id here is a broken id there.
                row.id,
                "yes" if row.id == self_id else "",
                row.status.value,
                listening,
                age,
                last_msg,
                row.cwd,
                row.title or "",
            ]
        )
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


def cmd_show(args: argparse.Namespace) -> None:
    path = _find_session_path(args.session_id)
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
