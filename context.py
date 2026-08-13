"""Single implementation of "what context are we acting in right now."

Two distinct questions, two distinct functions -- never conflate them:
- Reading/scoping ("what should `todo list`/`context tree`/`kb summary` show me right
  now"): resolve_context() -- an explicit --context narrows to that Context's subtree;
  with no override, resolves to None ("everywhere"). There is no ambient persisted
  default context -- one used to exist (CurrentContext) but it caused a stale
  context set once (e.g. switched for an unrelated task) to silently filter every
  later read for both sessions and days, without ever showing up in the output as
  a strange result -- only in a full re-read of the command's own scoping text. --context
  now only ever affects the single invocation it's passed on.
- Creating a new row ("what context does this new Goal/Todo/... get"): creation_context()
  -- an explicit --context, or the same fixed `inbox` fallback, so a fresh session can
  never silently create a record under some unrelated leftover context.

Every script that needs to know the active context should call one of these,
not query Context directly — this is the one place that logic lives.
"""

from __future__ import annotations

import argparse
from typing import Optional

from sqlalchemy.orm import Session

from models import Context

INBOX_CONTEXT_NAME = "inbox"


def resolve_context(session: Session, cli_override: Optional[str] = None) -> Optional[Context]:
    """Resolve the context a read-scoped command should act in.

    cli_override, if given, is a context name that applies for this call only -- if it
    doesn't exist yet, it's created as a new top-level Context (and a short "created new
    context" notice is printed; see kb_cli._util.scope_to_context), not a hard error. Absent
    cli_override, returns None -- "show everything, unscoped" -- there is no ambient default
    context to silently fall back to. Every caller must print what it resolved to so the
    scope is never invisible.
    """
    if cli_override is not None:
        context, created = Context.get_or_create_reporting(session, cli_override)
        if created:
            print(f"Created new top-level context {context.name!r} (see `kb context -h` to move/manage it).")
        return context
    return None


def creation_context(args: argparse.Namespace) -> Context:
    """The Context an `add` command should pin its new row to.

    An `add` without an explicit --context lands in the fixed `inbox` Context,
    so a fresh session can never silently create a record under an unrelated
    leftover context (this is exactly what caused Daily #22 to land under
    "palworld" instead of "hygiene"). Pass --context explicitly, or
    `kb <noun> update ID --context NAME` afterward to relocate out of inbox.
    """
    if args.context_explicit:
        context: Context = args.context
        return context
    return get_inbox_context(args.session)


def get_inbox_context(session: Session) -> Context:
    """The fixed top-level fallback Context -- used by creation_context() for any `add`
    with no explicit --context. Always exists (created on first use)."""
    return Context.get_or_create(session, INBOX_CONTEXT_NAME)
