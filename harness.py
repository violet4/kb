"""Detecting which agentic-coding-harness session is currently running, independent of
which harness or which build of that harness (e.g. Claude Code's npm package vs. its native
binary) is in use. Content lives here, not in kb_cli/, since it's a plain fact-finding
function any caller (a CLI command, a hook, kb_repl.py) can use -- not routing/argparse
wiring, which is what kb_cli/ holds.

Env var names are the mechanism actually available to a bare `kb <command>` invocation run
from an interactive shell inside a session (no JSON payload to read, unlike a hook). A hook
adapter that already has the harness's own JSON envelope on stdin (e.g.
harnesses/claude-code/notify-claude reading `.session_id`) should keep reading it directly
from there instead of calling this -- this function is for the "just a plain shell command,
no envelope available" case."""

import json
import os
from pathlib import Path

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


def session_transcript_title(path: Path) -> str | None:
    """The resolved title for a session transcript -- a user-set custom-title event if one
    exists, else the harness's own ai-title event, else the first user message. Same
    resolution order Claude Code's own session picker uses, so this always matches what a
    user sees as "the session name" in that harness. None if the transcript is empty/unreadable
    or carries no title-worthy content."""
    title = None
    custom_title = None
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

    resolved_title = custom_title or title
    if resolved_title is None:
        resolved_title = first_user_text
        if resolved_title is not None:
            resolved_title = " ".join(resolved_title.split())
            if len(resolved_title) > 70:
                resolved_title = resolved_title[:67] + "..."
        return resolved_title
    return " ".join(resolved_title.split())
