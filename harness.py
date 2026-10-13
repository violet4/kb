"""Facts about the agentic-coding harness kb runs under: which session is currently running,
independent of which harness or which build of that harness (e.g. Claude Code's npm package
vs. its native binary) is in use, and where a session's transcript is and what it holds.
Content lives here, not in kb_cli/, since it's plain fact-finding any caller (a CLI
command, a hook, kb_repl.py) can use -- not routing/argparse wiring, which is what kb_cli/
holds.

Env var names are the mechanism actually available to a bare `kb <command>` invocation run
from an interactive shell inside a session (no JSON payload to read, unlike a hook). A hook
adapter that already has the harness's own JSON envelope on stdin (e.g.
harnesses/claude-code/notify-claude reading `.session_id`) should keep reading it directly
from there instead of calling this -- this function is for the "just a plain shell command,
no envelope available" case."""

import json
import os
from pathlib import Path
from typing import NamedTuple

# Every env var name known to carry the current session ID, across every harness/build seen
# so far. Add a new name here (not a new function) when another harness or harness build is
# found to expose one -- this list is the single place that knowledge lives.
_SESSION_ID_ENV_VARS = ("CLAUDE_CODE_SESSION_ID",)  # Claude Code, npm package

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def current_session_id() -> str | None:
    """The current harness session's ID, or None if none is detectable (not running inside
    a known harness, or that harness's build doesn't expose one via env var)."""
    for var in _SESSION_ID_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return None


def find_session_transcript_path(session_id: str) -> Path | None:
    """Locate a Claude Code session transcript by its session_id (filename stem) across all
    projects, or None if no such transcript exists."""
    if not PROJECTS_DIR.is_dir():
        return None
    for project_dir in PROJECTS_DIR.iterdir():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.is_file():
            return candidate
    return None


class TranscriptSummary(NamedTuple):
    title: str
    message_count: int


def read_transcript_summary(path: Path) -> TranscriptSummary | None:
    """A Claude Code session transcript's title and message count, read in one pass, or None
    if it has no title and no user text. This is the one place a transcript file is parsed for
    these two fields. It has no cache of its own: callers read through
    TranscriptCache.get_or_refresh (models/agents/transcript_cache.py), which calls this only
    when the file's mtime changed.

    message_count is the number of real chat turns (type "user" or "assistant", the same
    definition list_chat_messages uses for what counts as a message) -- not the raw line
    count, which is dominated by bookkeeping events (attachment, mode, permission-mode, ...)
    unrelated to conversation content and would be a misleading size proxy."""
    title = None
    custom_title = None
    first_user_text = None
    message_count = 0
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue

            t = d.get("type")
            if t in ("user", "assistant"):
                message_count += 1
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

    resolved_title = custom_title or title
    if resolved_title is None:
        resolved_title = first_user_text
        if resolved_title is not None:
            resolved_title = " ".join(resolved_title.split())
            if len(resolved_title) > 70:
                resolved_title = resolved_title[:67] + "..."
    else:
        resolved_title = " ".join(resolved_title.split())

    if resolved_title is None:
        return None
    return TranscriptSummary(resolved_title, message_count)
