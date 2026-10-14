"""HarnessSession, one agent session of a harness."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

import psutil
from sqlalchemy import Boolean, Enum, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base, UtcDateTime, _now


def process_started_at(pid: int) -> Optional[datetime]:
    """When the process currently holding `pid` started, or None if no process holds it. A
    (pid, start time) pair identifies one process for its whole life; a pid alone does not."""
    try:
        return datetime.fromtimestamp(psutil.Process(pid).create_time(), timezone.utc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


class HarnessSessionStatus(enum.Enum):
    INFERRING = "inferring"
    IDLE = "idle"


class HarnessSessionKind(enum.Enum):
    """AGENT (the default) is a real `claude` CLI process, alive/dead by its own pid -- see
    is_alive(). HUMAN is a person participating in Channel messaging from a non-harness
    surface (the web UI's chat view) rather than a Claude Code session; it has no OS process
    of its own, so pid is a meaningless 0 sentinel and is_alive() is unconditionally True for
    this kind -- a human is reachable by definition, not by a liveness check. This is the
    schema-honest alternative to either faking a pid for a human row or loosening
    ChannelMessage.from_session to a nullable FK plus a shadow display-name column: every
    ChannelMessage.from_session still always resolves to a real, addressable HarnessSession
    row, agent or human, with no new nullable column and no unattributable message possible."""

    AGENT = "agent"
    HUMAN = "human"


class HarnessSession(Base):
    """One row per live harness session (a `claude` CLI process, or another harness's
    equivalent), registered at SessionStart and read by `kb sessions` for cross-session
    discovery/messaging -- see Goal #46. Named HarnessSession, not Session, since SQLAlchemy's
    own Session class is already imported under that name throughout this file.

    harness_id is the harness's own session id (harness.py:current_session_id(), a UUID for
    Claude Code), the identifier every external surface uses: CLI arguments, API payloads,
    transcript filenames. id is an integer surrogate that every other table references
    instead, since a session id is repeated on every row that points at a session and a
    36-character string costs roughly ten times an integer per row and per index entry.
    by_harness_id() is the one lookup from the external id to the row.

    Liveness for kind == AGENT is checked against the process at read time (is_alive()): a
    process with this pid must exist and have started at process_started_at, since a pid alone
    is reused by unrelated processes once the session's own process exits. A crashed or killed
    process therefore drops out of `kb sessions` output with no de-registration hook. One
    process can host several sessions in turn (`/clear` and `/resume` issue a new session id
    in the same process), so register() ends every other open row for the same pid. ended_at
    records the first time kb found a session ended, not the exact moment it ended; live()
    stamps it, so each later read checks only the open rows. Same-machine only (a pid doesn't
    resolve across hosts). kind == HUMAN skips the process check -- see HarnessSessionKind.

    status/last_active_at/last_response_at are populated only by hooks that actually observe
    those transitions (UserPromptSubmit -> INFERRING + bump last_active_at, Stop -> IDLE +
    bump last_response_at, PermissionRequest -> awaiting_permission) -- don't add a field here
    that no hook can honestly populate.
    is_listening is set/cleared by `kb sessions listen` itself on start and on exit (including
    a SIGTERM trap so a normally-killed listener doesn't leave it stuck true) -- but a SIGKILL,
    an OOM kill, or a harness that reaps the process without ever delivering SIGTERM all skip
    that exit path, and were all confirmed live (2026-08-17, kb Note #163) to leave is_listening
    permanently stuck true with no self-heal. listener_pid (the `kb sessions listen` subprocess's
    own pid, distinct from this row's own `pid` -- the harness process's pid, a different
    process) is what makes that recoverable: is_listening_live() below checks whether
    listener_pid still resolves before trusting the flag, the same pid-liveness pattern this
    class already uses for the row itself (is_alive() below) rather than a status flag with no
    external check."""

    __tablename__ = "harness_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    harness_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cwd: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[HarnessSessionKind] = mapped_column(
        Enum(HarnessSessionKind, create_constraint=True, validate_strings=True),
        nullable=False,
        default=HarnessSessionKind.AGENT,
    )
    status: Mapped[HarnessSessionStatus] = mapped_column(
        Enum(HarnessSessionStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=HarnessSessionStatus.IDLE,
    )
    # True from a PermissionRequest hook (which runs before Claude Code shows a permission
    # dialog) until the turn ends, the next prompt arrives, or an Esc is sent. No hook fires
    # when a dialog closes, so the flag can outlive its dialog for the rest of the turn; the
    # one thing it must never do is read False while a dialog is open, because a prompt
    # submitted then would answer the dialog.
    awaiting_permission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_listening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    listener_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    last_response_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    # Start time of the process at `pid` when it registered; None for HUMAN rows and for rows
    # whose process had already exited or been reused when this column was added.
    process_started_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)

    @classmethod
    def by_harness_id(cls, session: Session, harness_id: str) -> Optional[HarnessSession]:
        return session.scalars(select(cls).where(cls.harness_id == harness_id)).first()

    @classmethod
    def register(
        cls, session: Session, harness_id: str, cwd: str, pid: int, title: Optional[str] = None
    ) -> HarnessSession:
        """Called from a SessionStart hook, which fires on startup, resume, and `/clear`.
        Upserts -- a resumed session reuses the same harness session id, so this updates
        cwd/pid/title in place and reopens it rather than erroring on a duplicate key. Ends
        every other open AGENT row for the same pid: the process now hosts this session, so
        any earlier session in it is over, and a row from an earlier process that held the
        same pid is over too."""
        now = _now()
        row = cls.by_harness_id(session, harness_id)
        if row is None:
            row = cls(harness_id=harness_id, cwd=cwd, pid=pid, title=title)
            session.add(row)
        else:
            row.cwd = cwd
            row.pid = pid
            if title is not None:
                row.title = title
        row.process_started_at = process_started_at(pid)
        row.ended_at = None
        session.flush()
        for other in session.scalars(
            select(cls).where(
                cls.kind == HarnessSessionKind.AGENT,
                cls.pid == pid,
                cls.ended_at.is_(None),
                cls.id != row.id,
            )
        ):
            other.ended_at = now
        session.flush()
        return row

    @classmethod
    def get_or_create_human(cls, session: Session, display_name: str) -> HarnessSession:
        """One HarnessSession row per distinct human display name -- harness_id is a stable
        "human:<display_name>" string (its own id namespace, never collides with a harness's
        own session id) so the same person sending from the web UI under an unchanged display
        name always resolves to the same row rather than growing a new one per message."""
        harness_id = f"human:{display_name}"
        existing = cls.by_harness_id(session, harness_id)
        if existing is not None:
            return existing
        row = cls(harness_id=harness_id, cwd="", pid=0, title=display_name, kind=HarnessSessionKind.HUMAN)
        session.add(row)
        session.flush()
        return row

    def is_alive(self) -> bool:
        """For an AGENT row: not ended, and the process at `pid` is the one that registered
        (same start time), not a later process that reused the pid."""
        if self.kind == HarnessSessionKind.HUMAN:
            return True
        if self.ended_at is not None or self.process_started_at is None:
            return False
        started = process_started_at(self.pid)
        return started is not None and abs((started - self.process_started_at).total_seconds()) < 1

    def is_listening_live(self) -> bool:
        """is_listening, corrected for a listener process that died without clearing its own
        flag (SIGKILL, OOM, a harness reap that skips SIGTERM -- see this class's docstring).
        False whenever the flag is set but listener_pid no longer resolves, so a caller never
        has to trust a self-reported flag with no external check -- the same reasoning that
        already makes is_alive() a pid check instead of a status column."""
        if not self.is_listening:
            return False
        if self.listener_pid is None:
            return False
        return psutil.pid_exists(self.listener_pid)

    @classmethod
    def live(cls, session: Session) -> list[HarnessSession]:
        """Every live AGENT session -- what `kb sessions`/the frontend's Agents page lists.
        Deliberately excludes HUMAN rows even though is_alive() is unconditionally True for
        them: this method answers "which Claude Code sessions can I message/see the status
        of," a different question from "who can post in a Channel" (every messaging query
        that needs to include humans, e.g. Channel membership, goes through HarnessSession
        directly or ChannelSubscription, never through this method).

        Checks only open rows (ended_at unset) and stamps ended_at on each one it finds no
        longer alive, so a session is checked against the process table until the first read
        that finds it ended and never again. Flushes; the caller commits."""
        live = []
        now = _now()
        open_rows = session.scalars(
            select(cls).where(cls.kind == HarnessSessionKind.AGENT, cls.ended_at.is_(None))
        ).all()
        for row in open_rows:
            if row.is_alive():
                live.append(row)
            else:
                row.ended_at = now
        session.flush()
        return live

    @classmethod
    def stale_listeners(cls, session: Session) -> list[HarnessSession]:
        """Every row with is_listening stuck True whose listener_pid no longer resolves (see
        is_listening_live()'s docstring for how this happens: SIGKILL/OOM/harness-reap skipping
        the listen loop's own SIGTERM-triggered cleanup). Deliberately not scoped to live() --
        a session itself can be gone (harness closed) while its is_listening flag is still
        stuck true, and that row is exactly as safe to clear as one whose session is alive."""
        return [
            row
            for row in session.scalars(select(cls).where(cls.is_listening.is_(True))).all()
            if not row.is_listening_live()
        ]

    @classmethod
    def clear_stale_listeners(cls, session: Session) -> list[HarnessSession]:
        """DB-only cleanup: clears is_listening/listener_pid on stale_listeners() rows. Never
        touches an OS process -- unlike killing by pid (see kb Note #159's postmortem, 2026-08-17:
        an agent trying to stop its own session's background listener instead killed `kb sessions
        listen` processes for other live sessions by grepping `ps aux`), this only ever corrects
        this row's own bookkeeping for a listener process that has *already* exited on its own.
        A live listener (listener_pid still resolves) is never a candidate, live or not-yours --
        so this is always safe to run broadly, including automatically, with no scoping needed."""
        rows = cls.stale_listeners(session)
        for row in rows:
            row.is_listening = False
            row.listener_pid = None
        return rows

    @classmethod
    def detached_listeners(cls, session: Session) -> list[HarnessSession]:
        """Every row whose listener is genuinely alive (is_listening_live() True) but whose
        own session is not (is_alive() False) -- a `kb sessions listen` process that outlived
        the harness session that spawned it. The harness process itself may still be running
        under a newer session: `/clear` issues a new session id in the same process, and
        register() ends the old row while its background listener keeps polling.

        Distinct from stale_listeners(): that method covers a listener that already died
        without clearing its own flag (DB bookkeeping wrong, no live process to worry about).
        This one is the opposite -- the process is still alive and will poll forever, since
        nothing will ever attach to read its background-task-completion notification again.

        DB-provable, not a `ps aux` grep -- same safety bar clear_stale_listeners() already
        meets (see kb Note #159's postmortem) -- so this is safe to compute broadly, including
        automatically. Unlike clear_stale_listeners() though, correcting this case requires
        actually killing listener_pid, not just fixing the DB row -- see
        kill_detached_listeners()."""
        return [
            row
            for row in session.scalars(select(cls).where(cls.is_listening.is_(True))).all()
            if row.is_listening_live() and not row.is_alive()
        ]

    @classmethod
    def kill_detached_listeners(cls, session: Session) -> list[tuple[HarnessSession, int]]:
        """Terminates (SIGTERM, falling back to SIGKILL if still alive after) every
        detached_listeners() row's listener_pid, then clears is_listening/listener_pid on that
        row -- the actual-process-kill counterpart to clear_stale_listeners()'s DB-only clear.

        Safe to run broadly/automatically for the same reason detached_listeners() is: each
        candidate pid is read from this row's own listener_pid, provably alive (is_listening_live()
        already confirmed it resolves) and provably orphaned (is_alive() confirmed the owning
        harness does not), never guessed from a process-list grep -- so unlike the Note #159
        postmortem this can't collide with another session's live listener.

        Returns (row, killed_pid) pairs rather than bare rows -- row.listener_pid is cleared
        to None as part of this same call, so a caller that wants to report which pid it just
        killed (e.g. cmd_listen's startup sweep) can't read it back off the row afterwards."""
        rows = cls.detached_listeners(session)
        result: list[tuple[HarnessSession, int]] = []
        for row in rows:
            pid = row.listener_pid
            # detached_listeners() only returns rows that passed is_listening_live(), which
            # already requires listener_pid is not None -- assert makes that cross-method
            # invariant explicit and checkable rather than re-widening the type to Optional.
            assert pid is not None, "detached_listeners() row must have a live listener_pid"
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=2)
                except psutil.TimeoutExpired:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            result.append((row, pid))
            row.is_listening = False
            row.listener_pid = None
        return result

    def __repr__(self) -> str:
        listening_str = " listening" if self.is_listening else ""
        return f"<HarnessSession {self.harness_id[:8]} [{self.status.value}]{listening_str} cwd={self.cwd!r}>"
