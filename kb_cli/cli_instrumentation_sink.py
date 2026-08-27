"""Pure mapping from a cli_instrumentation invocation payload to CliInvocation
constructor kwargs -- split out of the `kb` script itself (which is not
importable: no .py extension, and importing it would execute top-level
argument parsing) so this mapping is independently testable against the
`db_session` fixture, without a test needing to shell out to `./kb` against
the real on-disk database."""

import json
from typing import Any


def should_record(payload: dict[str, Any]) -> bool:
    """Whether a cli_instrumentation payload is worth writing a CliInvocation row for.
    Excludes only a SUCCESSFUL `kb hooks ...` invocation -- `kb hooks` is Claude Code's
    own tool-hook machinery firing constantly (thousands/day) with near-zero variation
    when it works, so its successes are storage spent for no analytical value (see kb
    Instruction root's proactive-friction-surfacing rationale in CliInvocation's own
    docstring in models.py). A FAILING `kb hooks ...` invocation is still recorded --
    e.g. a detector blocking a dangerous command, or a real bug in a hook's own code
    (see kb Note on SessionMessage.mark_read()'s missing-args TypeError, found via this
    table) -- failures are exactly the rare, worth-keeping signal this exists to catch.
    Checked against the exact resolved top-level subcommand (`command.split()[0]`), not
    a substring/prefix match against the raw command string, so an unrelated future
    command that happens to start with the same letters is never misclassified."""
    if not payload["success"]:
        return True
    words = payload["command"].split()
    return not words or words[0] != "hooks"


def invocation_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a cli_instrumentation record() payload to CliInvocation(**kwargs)."""
    return {
        "command": payload["command"],
        "subcommand": payload.get("subcommand"),
        "success": payload["success"],
        "error": payload.get("error"),
        "duration_ms": payload["duration_ms"],
        "args_json": json.dumps(payload.get("args", {}), default=str),
    }
