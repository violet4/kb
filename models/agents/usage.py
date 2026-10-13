"""CliInvocation and UsageSample, kb's own usage telemetry."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UtcDateTime, _now


class CliInvocation(Base):
    """One record per top-level `kb` CLI invocation -- command text, resolved subcommand
    path, timing, whether it succeeded, the error message if it didn't, and a size-capped
    snapshot of parsed args. Written by the optional `cli_instrumentation` library (a
    private, not-yet-public dependency -- see the `kb` script's own ImportError fallback
    and kb_cli/stats.py) via the `kb` script's own entry point, independent of any one
    subcommand knowing about it, so every invocation is covered without each kb_cli/*.py
    module having to opt in. Without cli_instrumentation installed, this table simply stays
    empty -- nothing else in kb depends on it being populated. The point is to make CLI
    friction (a confusing error, a command that fails the same way repeatedly) and CLI usage
    patterns (unused commands, commonly used flags) queryable (`kb stats`) instead of relying
    on friction being reported by hand each time it's hit -- see kb Instruction root, "the
    tree's own re-check mechanisms... exist for exactly this: surfacing friction proactively,
    not after the fact," applied to the CLI's own errors and usage.

    `args_json` stores cli_instrumentation's already-truncated args snapshot verbatim, as a
    single JSON column rather than normalized per-arg columns/rows -- its shape varies by
    subcommand and is expected to change as instrumentation needs evolve, and decomposing it
    is a decision to make later, driven by an actual query or storage-size need that shows up
    in practice, not up front."""

    __tablename__ = "cli_invocation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    subcommand: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    args_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        status = "ok" if self.success else "error"
        return f"<CliInvocation #{self.id} [{status}] {self.command!r}>"


class UsageSample(Base):
    """A single point-in-time reading of `claude -p /usage`'s session/week percentages,
    recorded by `kb_cli.usage.fetch_usage()` each time it performs a real (non-cached) fetch --
    never on a cache hit, so samples are naturally throttled to at most 1/minute by
    `_CACHE_MAX_AGE` regardless of how many CLI/web callers ask in that window. The point is an
    over-time record (`kb stats usage --history`, future charts) that can answer "was that spike
    10 minutes or 2 hours" after the fact, not just show the current instantaneous reading.
    `raw_text` samples (no usage yet) are not recorded -- there is nothing numeric to chart."""

    __tablename__ = "usage_sample"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    session_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    session_resets_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    week_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    week_resets_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    def __repr__(self) -> str:
        return f"<UsageSample #{self.id} session={self.session_pct}% week={self.week_pct}%>"
