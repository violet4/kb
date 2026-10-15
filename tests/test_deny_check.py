"""harnesses/claude-code/deny-check: a blocking detector's stdout becomes a deny, silence allows,
and a detector that cannot run denies rather than allows (fail closed)."""

import json
import os
import subprocess
from pathlib import Path

DENY_CHECK = Path(__file__).parent.parent / "harnesses" / "claude-code" / "deny-check"


def _run(command: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        [str(DENY_CHECK), "git-add-a-check"],
        input=command,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=True,
    ).stdout


def _decision(output: str) -> str:
    return str(json.loads(output)["hookSpecificOutput"]["permissionDecision"])


def test_silent_detector_allows() -> None:
    assert _run("ls\n") == "{}"


def test_detector_reason_denies() -> None:
    assert _decision(_run("git add " + "-A\n")) == "deny"


def test_detector_that_cannot_run_denies() -> None:
    output = _run("ls\n", env={"KB_DB_PATH": "/nonexistent/kb.db"})
    assert _decision(output) == "deny"
    assert "could not run" in json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]
