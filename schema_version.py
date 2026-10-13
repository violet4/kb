"""Whether the database schema matches this code, and who has the database open.

The server migrates on startup (server.py); every other process checks pending_count() and
refuses to run against a schema older than its models. Reading the revision graph from the
version files' own `revision`/`down_revision` lines, rather than through alembic's
ScriptDirectory, keeps the check to a few milliseconds: loading the script directory imports
every migration module, about 400 ms, too slow for every `kb` command.
"""

import re
import sqlite3
import time
from pathlib import Path

import psutil

KB_DIR = Path(__file__).parent
DB_PATH = KB_DIR / "data" / "kb.db"
ALEMBIC_INI = KB_DIR / "alembic.ini"
_VERSIONS_DIR = KB_DIR / "alembic" / "versions"

_REVISION_RE = re.compile(r"^revision\s*(?::[^=]*)?=\s*['\"](\w+)['\"]", re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r"^down_revision\s*(?::[^=]*)?=\s*(.*)$", re.MULTILINE)
_REVISION_ID_RE = re.compile(r"['\"](\w+)['\"]")

UPGRADE_HINT = f"{KB_DIR / 'scripts' / 'db' / 'upgrade'} (or restart the kb server, which migrates on startup)"


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


def pending_count() -> int:
    """How many migrations stand between the database and this code's head. A database at a
    revision this code does not know (migrated by newer code) counts as current."""
    graph = revision_graph()
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
