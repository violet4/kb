"""Single implementation of "what context are we acting in right now."

Every script that needs to know the active context should call resolve_context(),
not look up CurrentContext or Context directly — this is the one place that logic lives.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from sqlalchemy.orm import Session

from models import Context, CurrentContext

KB_CONTEXT_ENV_VAR = "KB_CONTEXT"


def resolve_context(session: Session, cli_override: Optional[str] = None) -> Optional[Context]:
    """Resolve the context a command should act in.

    cli_override, if given, is a context name that applies for this call only —
    it never changes the persisted current context (use switch_current() for that).
    Absent that, the KB_CONTEXT environment variable (see `kb context switch --local`)
    lets one shell/tab act in a different context from the persisted default without
    affecting any other shell reading the same database.
    """
    if cli_override is not None:
        return Context.get_existing(session, cli_override)
    env_name = os.environ.get(KB_CONTEXT_ENV_VAR)
    if env_name:
        return Context.get_existing(session, env_name)
    return CurrentContext.get(session)


def warn_ambient_context(
    args: argparse.Namespace, entity_label: str, cli_name: Optional[str] = None, new_id: Optional[int] = None
) -> None:
    """Print a warning after an `add` command pins a new entity to the ambient
    current context because --context wasn't passed explicitly.

    Silent ambient fallback is exactly what caused Daily #22 to land under
    "palworld" instead of "hygiene" -- surfacing it here makes the fallback
    visible instead of a silent surprise, without forcing --context on every call.

    cli_name/new_id, if both given, name the `kb <cli_name> update <new_id>` command
    that corrects the record just created -- only pass these for entities whose CLI
    actually has an `update --context` (Goal/Idea/Daily/Todo as of this writing; Timer
    and LogEntry don't, being short-lived/point-in-time, so they're called with neither).
    """
    if args.context_explicit or args.context is None:
        return
    msg = f"note: {entity_label} using ambient context {args.context.name!r}."
    if cli_name and new_id is not None:
        msg += f" To fix: kb {cli_name} update {new_id} --context NAME"
    else:
        msg += " Pass --context next time to override."
    print(msg, file=sys.stderr)


def switch_current(session: Session, name: str) -> Context:
    """Change the persisted current context. Raises if `name` doesn't already
    exist -- create it explicitly first with `kb context add NAME`."""
    context = Context.get_existing(session, name)
    CurrentContext.set(session, context)
    return context
