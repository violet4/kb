"""Single implementation of "what context are we acting in right now."

Two distinct questions, two distinct functions -- never conflate them:
- Reading/scoping ("what should `todo list`/`context tree`/`kb summary` show me right
  now"): resolve_context() -- follows the persisted CurrentContext (shared across every
  shell -- there is no per-shell override; a `--local`/$KB_CONTEXT escape hatch existed
  before but was never actually intuitive to use, so it was removed rather than kept as
  a second, rarely-used way to answer this question). If CurrentContext has never been
  set, this does NOT fall through to "show everything" (a fresh session dumping the
  entire tree is the kind of overshoot "keep context small" rules out) -- it falls to the
  same fixed `inbox` Context creation_context() uses. Either way, the caller must announce
  what it resolved to (see kb_cli._util.scope_to_context) so the scope is never invisible.
- Creating a new row ("what context does this new Goal/Todo/... get"): creation_context()
  -- never ambient, not even via CurrentContext. An explicit --context, or the same fixed
  `inbox` fallback, so a fresh session can never silently create a record under an
  unrelated leftover current context.

Every script that needs to know the active context should call one of these,
not look up CurrentContext or Context directly — this is the one place that logic lives.
"""

from __future__ import annotations

import argparse
from typing import Optional

from sqlalchemy.orm import Session

from models import Context, CurrentContext

INBOX_CONTEXT_NAME = "inbox"


def resolve_context(session: Session, cli_override: Optional[str] = None) -> Context:
    """Resolve the context a read-scoped command should act in.

    cli_override, if given, is a context name that applies for this call only —
    it never changes the persisted current context (use switch_current() for that).
    Absent that, this follows the persisted CurrentContext (shared by every shell).
    If CurrentContext has never been set, this falls back to the same fixed `inbox`
    Context creation_context() uses — never "show everything". A brand-new session
    with no context ever chosen should see a small, known, filtered view (whatever's
    in `inbox`), not the entire tree; unscoped visibility is exactly the kind of
    overshoot the "keep context small" principle rules out. Use `--all` on the
    calling command to deliberately see everything instead.
    """
    if cli_override is not None:
        return Context.get_existing(session, cli_override)
    return CurrentContext.get(session) or get_inbox_context(session)


def creation_context(args: argparse.Namespace) -> Context:
    """The Context an `add` command should pin its new row to.

    Creation never falls back to the ambient CurrentContext -- that's for read-scoping
    only (see resolve_context). An `add` without an explicit
    --context lands in the fixed `inbox` Context instead, so a fresh session can
    never silently create a record under an unrelated leftover context (this is
    exactly what caused Daily #22 to land under "palworld" instead of "hygiene").
    Pass --context explicitly, or `kb <noun> update ID --context NAME` afterward
    to relocate out of inbox.
    """
    if args.context_explicit:
        context: Context = args.context
        return context
    return get_inbox_context(args.session)


def get_inbox_context(session: Session) -> Context:
    """The fixed top-level fallback Context -- used by creation_context() for any `add`
    with no explicit --context, and by resolve_context() for read-scoping when
    CurrentContext has never been switched to anything. Always exists (created on
    first use) -- distinct from the persisted CurrentContext, which can point anywhere
    and only ever changes via an explicit `kb context switch`."""
    return Context.get_or_create(session, INBOX_CONTEXT_NAME)


def switch_current(session: Session, name: str) -> Context:
    """Change the persisted current context. Raises if `name` doesn't already
    exist -- create it explicitly first with `kb context add NAME`."""
    context = Context.get_existing(session, name)
    CurrentContext.set(session, context)
    return context
