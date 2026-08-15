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

import os

# Every env var name known to carry the current session ID, across every harness/build seen
# so far. Add a new name here (not a new function) when another harness or harness build is
# found to expose one -- this list is the single place that knowledge lives.
_SESSION_ID_ENV_VARS = ("CLAUDE_CODE_SESSION_ID",)  # Claude Code, npm package


def current_session_id() -> str | None:
    """The current harness session's ID, or None if none is detectable (not running inside
    a known harness, or that harness's build doesn't expose one via env var)."""
    for var in _SESSION_ID_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return None
