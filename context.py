"""Single implementation of "what context are we acting in right now."

Every script that needs to know the active context should call resolve_context(),
not look up CurrentContext or Context directly — this is the one place that logic lives.
"""
from __future__ import annotations

from typing import Optional

from models import Context, CurrentContext


def resolve_context(cli_override: Optional[str] = None) -> Optional[Context]:
    """Resolve the context a command should act in.

    cli_override, if given, is a context name that applies for this call only —
    it never changes the persisted current context (use switch_current() for that).
    """
    if cli_override is not None:
        return Context.get_or_create(cli_override)
    return CurrentContext.get()


def switch_current(name: str) -> Context:
    """Change the persisted current context."""
    context = Context.get_or_create(name)
    CurrentContext.set(context)
    return context
