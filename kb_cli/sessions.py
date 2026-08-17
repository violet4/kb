"""Live harness-session discovery and cross-session messaging (see kb Goal #46), plus the
original Claude Code CLI transcript listing this module used to be limited to (now under
`kb sessions history` / `kb sessions list --all`).

`kb sessions` (bare, or `list`) shows only currently-live sessions -- registered via
HarnessSession.register (called from a SessionStart hook) and filtered to pid-alive rows, not
parsed from *.jsonl transcripts. That parsing still exists, moved to `history`, for browsing
past sessions by title/timestamp the way this module always did.

Mailbox is a DM, not a channel -- send/inbox operate on one session at a time, addressed by
harness session id. See Note #157 for why FileChanged (a filesystem-watch hook) doesn't give
true idle-session async delivery in Claude Code, and Goal #46 for the resulting two-layer
delivery design this module's `inbox` (checked from UserPromptSubmit) and `listen` (an optional
foreground poll loop) implement.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import psutil

from harness import current_session_id
from models import HarnessSession, SessionMessage

from kb_cli._util import print_table, resolve_text_arg

_PROJECTS_DIR = Path.home() / ".claude" / "projects"

_LISTEN_POLL_SECONDS = 5


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
    args.session.commit()


def cmd_list(args: argparse.Namespace) -> None:
    if args.all:
        cmd_history(args)
        return
    live = HarnessSession.live(args.session)
    if not live:
        print("No live sessions.")
        return
    self_id = current_session_id()
    headers = ["Session", "You?", "Status", "Listening", "Cwd", "Title"]
    rows = []
    for row in live:
        rows.append(
            [
                # Full id, not truncated -- kb sessions send needs to copy-paste this
                # directly, and a shortened id here is a broken id there.
                row.id,
                "yes" if row.id == self_id else "",
                row.status.value,
                "yes" if row.is_listening else "",
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
    msg = SessionMessage.send(
        args.session, from_session=from_session, to_session=args.to, body=resolve_text_arg(args.body)
    )
    args.session.commit()
    print(msg)

    if not recipient.is_alive():
        print(
            f"Note: session {args.to} is not currently running -- it will likely never read this message unless "
            "resumed. Don't wait on a reply; investigate the question directly instead."
        )


def cmd_inbox(args: argparse.Namespace) -> None:
    """Called both by a person checking their own session's mail and by the
    UserPromptSubmit hook adapter (see kb Goal #46 Layer 1) -- unread messages are
    printed and marked read in the same call, matching this design's read_at-only
    state (no separate archive/dismiss step)."""
    to_session = _require_session_id()
    messages = SessionMessage.inbox(args.session, to_session, unread_only=not args.all)
    if not messages:
        if not args.quiet:
            print("No new messages.")
        return
    for msg in messages:
        print(f"From {msg.from_session} at {msg.created_at.isoformat()}:\n  {msg.body}\n")
        if not args.all:
            msg.mark_read()
    args.session.commit()


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
    row = args.session.get(HarnessSession, to_session)
    if row is None:
        print(
            f"kb sessions listen: session {to_session} is not registered -- run `kb hooks session-register` "
            "once (covers a session that started before the SessionStart hook existed, or any other reason "
            "registration didn't happen), then retry"
        )
        raise SystemExit(1)
    if row.is_listening:
        # Refuse rather than try to kill the existing one -- a run_in_background shell is
        # entirely local to the harness session that started it, with no pid or handle
        # visible to this process, so there is no safe way to terminate it from here.
        # Two concurrent listeners for the same session would double-poll, race on
        # mark_read(), and stomp on is_listening in each other's `finally` block --
        # refusing to start a second one is the correct fix, not cross-process termination.
        print(
            f"kb sessions listen: already listening for session {to_session} (per kb's own records) -- "
            "check your own harness's background-task list (not another kb command) for the existing one "
            "rather than starting a second listener for the same session."
        )
        raise SystemExit(1)
    row.is_listening = True
    args.session.commit()
    try:
        while True:
            messages = SessionMessage.inbox(args.session, to_session, unread_only=True)
            if messages:
                for msg in messages:
                    print(f"From {msg.from_session} at {msg.created_at.isoformat()}:\n  {msg.body}\n")
                    msg.mark_read()
                args.session.commit()
                # stdout is fully buffered (not line-buffered) once it's not a TTY, which is
                # always true for a run_in_background process -- an explicit flush here is
                # required so the printed message is actually visible in the captured output
                # before the process exits, rather than depending on Python's own exit-time
                # flush (which was silently lost at least once: message #8, 2026-08-17 --
                # DB showed a correct mark_read()+commit but no delivered text ever appeared
                # in the backgrounded task's output).
                sys.stdout.flush()
                return
            time.sleep(_LISTEN_POLL_SECONDS)
    finally:
        row.is_listening = False
        args.session.commit()


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

    inbox_parser = sub.add_parser("inbox", help="Show and mark-read this session's own new messages")
    inbox_parser.add_argument(
        "--all", action="store_true", help="Show every message, read or not, without marking anything read"
    )
    inbox_parser.add_argument("--quiet", action="store_true", help="Print nothing when there are no new messages")
    inbox_parser.set_defaults(func=cmd_inbox)

    listen_parser = sub.add_parser(
        "listen",
        help="Poll this session's own inbox in a loop, exiting the moment new mail arrives -- run via run_in_background",
    )
    listen_parser.set_defaults(func=cmd_listen)

    parser.set_defaults(func=cmd_list)
