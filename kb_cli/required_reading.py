"""Required reading: the instruction nodes an agent session must read before it writes a file.

A node in either tree, the system tree (`kb si`) or the user's own tree (`kb i`), lists
write_globs: space-separated globs matched against the written file's path. `*` crosses `/`,
so `*.py` matches a Python file anywhere and `*/AGENTS.md` any AGENTS.md; `~` expands. The
`required-reading-check` hook asks `unread_for` before each write and blocks it, naming the
nodes to read, while any matching node is unread. A reminder listing unopened nodes goes
unacted on; a block naming them gets them read, which is why this is a gate.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from kb_cli.shell_command import without_heredoc_bodies

WRITE_GLOBS_HELP = (
    "Space-separated globs of files a session must not write until it has read this node, e.g. "
    "'*.py' or '*/AGENTS.md' (* crosses /); pass \"\" to clear"
)

# Harness and scratch state, never gated.
_EXEMPT_RE = re.compile(r"(?:^|/)\.claude/|^/tmp/")


def matches(write_globs: str, path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, os.path.expanduser(glob)) for glob in write_globs.split())


def session_reads(session: Session, entity_type: str) -> Optional[set[int]]:
    """The ids of every `entity_type` record this agent session has read, or None when no
    registered agent session is detectable (nothing recorded to check against)."""
    from harness import current_session_id
    from models.agents.harness_session import HarnessSession
    from models.journal.journal import Journal

    harness_id = current_session_id()
    row = HarnessSession.by_harness_id(session, harness_id) if harness_id else None
    if row is None:
        return None
    return Journal.read_ids(session, entity_type, row.id)


def unread_for(session: Session, path: str) -> list[str]:
    """`kb si show`/`kb i show` commands for every node whose write_globs match `path` and
    which this agent session has not read; empty outside an agent session or for exempt
    paths."""
    from kb_cli import si_files
    from kb_cli._util import not_deleted
    from models.knowledge.instruction import Instruction

    if _EXEMPT_RE.search(path):
        return []
    commands = []
    si_read = session_reads(session, "SiNode")
    if si_read is not None:
        for node in si_files.list_nodes():
            if matches(node.write_globs, path) and int(node.id) not in si_read:
                commands.append(f"kb si show {node.title}")
    i_read = session_reads(session, "Instruction")
    if i_read is not None:
        query = not_deleted(select(Instruction).where(Instruction.write_globs != ""), Instruction)
        for row in session.scalars(query):
            if matches(row.write_globs, path) and row.id not in i_read:
                commands.append(f"kb i show {row.title}")
    return commands


# The files a Bash command writes, as far as its text shows: `text sub`/`text replace --file X`
# and `>`/`>>`/`tee` targets. Anything else (sed -i, a script) is invisible here.
_COMMAND_TARGET_RES = (
    re.compile(r"\btext\s+(?:sub|replace)\b[^\n|;&]*--file\s+([^\s|;&]+)"),
    re.compile(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*([^\s>|;&()]+)"),
)


# A `cd DIR` that is a whole step of a command (between `&&`, `||`, `;`, or newlines).
_COMMAND_STEP_SPLIT_RE = re.compile(r"&&|\|\||;|\n")
_CD_RE = re.compile(r"^\s*cd\s+([^\s$`]+)\s*$")


def command_targets(command: str, cwd: Optional[str] = None) -> list[str]:
    """The files `command` writes, as far as its text shows. With `cwd` (the directory the
    command starts in), a relative target is resolved against it, following each `cd DIR`
    step before the write, so `cd /tmp/x && cat > a.py` names /tmp/x/a.py; without it,
    relative targets stay relative. A `cd` to anything but a plain path leaves the directory
    unchanged."""
    targets = []
    here = cwd
    for step in _COMMAND_STEP_SPLIT_RE.split(without_heredoc_bodies(command)):
        if here is not None and (cd := _CD_RE.match(step)):
            here = os.path.normpath(os.path.join(here, os.path.expanduser(cd.group(1).strip("'\""))))
            continue
        for regex in _COMMAND_TARGET_RES:
            for target in regex.findall(step):
                if target.startswith("/dev/"):
                    continue
                if here is not None:
                    target = os.path.normpath(os.path.join(here, os.path.expanduser(target)))
                targets.append(target)
    return targets
