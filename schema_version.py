"""Whether the database schema matches this code, and who has the database open.

The server migrates on startup (server.py); every other process checks pending_count() and
refuses to run against a schema older than its models. Reading the revision graph from the
version files' own `revision`/`down_revision` lines, rather than through alembic's
ScriptDirectory, keeps the check to a few milliseconds: loading the script directory imports
every migration module, about 400 ms, too slow for every `kb` command.
"""

import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path

import psutil

KB_DIR = Path(__file__).parent
# The one definition of where the database lives (models/db.py and alembic/env.py read it here).
# KB_DB_PATH points a process at another database file, e.g. a test's throwaway copy.
DB_PATH = Path(os.environ["KB_DB_PATH"]) if os.environ.get("KB_DB_PATH") else KB_DIR / "data" / "kb.db"
ALEMBIC_INI = KB_DIR / "alembic.ini"
_VERSIONS_DIR = KB_DIR / "alembic" / "versions"

_REVISION_RE = re.compile(r"^revision\s*(?::[^=]*)?=\s*['\"](\w+)['\"]", re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r"^down_revision\s*(?::[^=]*)?=\s*(.*)$", re.MULTILINE)
_REVISION_ID_RE = re.compile(r"['\"](\w+)['\"]")

UPGRADE_SCRIPT = KB_DIR / "scripts" / "db" / "upgrade"
UPGRADE_HINT = f"{UPGRADE_SCRIPT} (or restart the kb server, which migrates committed migrations on startup)"


def revision_graph() -> dict[str, set[str]]:
    """Each revision in the version files mapped to the revisions it follows (empty for
    the first; several for a merge)."""
    graph: dict[str, set[str]] = {}
    for path in _VERSIONS_DIR.glob("*.py"):
        text = path.read_text()
        revision = _REVISION_RE.search(text)
        down = _DOWN_REVISION_RE.search(text)
        if revision is None or down is None:
            continue
        graph[revision.group(1)] = set(_REVISION_ID_RE.findall(down.group(1)))
    return graph


def code_heads(graph: dict[str, set[str]]) -> set[str]:
    """The revisions no other revision follows: what `alembic upgrade head` migrates to."""
    followed = set().union(*graph.values()) if graph else set()
    return set(graph) - followed


def db_revisions() -> set[str]:
    """The revisions the database is stamped at; empty for a database never migrated."""
    if not DB_PATH.exists():
        return set()
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        try:
            return {row[0] for row in conn.execute("SELECT version_num FROM alembic_version")}
        except sqlite3.OperationalError:
            return set()


def pending_count(graph: dict[str, set[str]] | None = None) -> int:
    """How many migrations of graph (default: every version file) stand between the database
    and its head. A database at a revision the graph does not know (migrated by newer code, or
    by a migration left out of the graph) counts as current."""
    graph = revision_graph() if graph is None else graph
    stamped = db_revisions()
    applied: set[str] = set()
    frontier = [rev for rev in stamped if rev in graph]
    if stamped and not frontier:
        return 0
    while frontier:
        rev = frontier.pop()
        if rev not in applied:
            applied.add(rev)
            frontier.extend(graph.get(rev, ()))
    return len(set(graph) - applied)


def db_holders() -> list[psutil.Process]:
    """Every other process with the database (or its WAL file) open."""
    paths = {str(DB_PATH.resolve()), f"{DB_PATH.resolve()}-wal"}
    holders = []
    for proc in psutil.process_iter():
        if proc.pid == psutil.Process().pid:
            continue
        try:
            if any(f.path in paths for f in proc.open_files()):
                holders.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return holders


def wait_until_db_closed(timeout_seconds: float) -> list[psutil.Process]:
    """Wait for every other process to close the database, up to timeout_seconds; returns
    the processes still holding it (empty once it is closed). kb's CLI commands and hooks
    hold it for well under a second, so a short wait outlasts them."""
    deadline = time.monotonic() + timeout_seconds
    holders = db_holders()
    while holders and time.monotonic() < deadline:
        time.sleep(0.2)
        holders = db_holders()
    return holders


def describe(proc: psutil.Process) -> str:
    try:
        return f"pid {proc.pid}: {' '.join(proc.cmdline())}"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return f"pid {proc.pid}"


def _revision_of(path: Path) -> str | None:
    match = _REVISION_RE.search(path.read_text()) if path.exists() else None
    return match.group(1) if match else None


def uncommitted_revisions() -> set[str]:
    """Revisions whose version file is untracked or differs from git HEAD: written but not yet
    reviewed. Empty when git or the repository is unavailable (an installed copy), where every
    migration counts as committed."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", str(_VERSIONS_DIR)],
            cwd=KB_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    revisions = set()
    for line in result.stdout.splitlines():
        path = KB_DIR / line[3:].strip()
        if path.suffix == ".py" and (revision := _revision_of(path)) is not None:
            revisions.add(revision)
    return revisions


def committed_graph(graph: dict[str, set[str]], uncommitted: set[str]) -> dict[str, set[str]]:
    """The graph without the uncommitted revisions and every revision that follows one: what
    the server's startup migration may apply."""
    excluded = set(uncommitted)
    grew = True
    while grew:
        grew = False
        for rev, follows in graph.items():
            if rev not in excluded and follows & excluded:
                excluded.add(rev)
                grew = True
    return {rev: follows for rev, follows in graph.items() if rev not in excluded}
