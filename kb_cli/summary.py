"""Print an overview of active Goals/Todos/overdue contacts/wishlist/inbox."""

import argparse
import sys
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from models import Context, CurrentContext, Daily, DailyTier, Goal, Idea, InboxItem, Person, Todo, Wishlist


def anki_section(session: Session) -> str | None:
    try:
        from anki.collection import Collection
    except ImportError:
        return "=== ANKI ===\nanki package not installed — uv sync --project ~/kb"

    from kb_cli.anki import DEFAULT_COLLECTION

    if not DEFAULT_COLLECTION.exists():
        return None
    try:
        col = Collection(str(DEFAULT_COLLECTION))
    except Exception:
        return "=== ANKI ===\nAnki is currently open — close it to see due-card count."
    try:
        due = sum(col.sched.counts())
    finally:
        col.close()

    if due == 0:
        return None
    return f"=== ANKI ===\n{due} card(s) due — kb anki decks"


def dailies_section(session: Session) -> str | None:
    critical = Daily.due(session, domain="irl", tier=DailyTier.CRITICAL)
    all_due = Daily.due(session)
    non_critical_irl = [d for d in all_due if d.domain == "irl" and d.tier != DailyTier.CRITICAL]
    game = [d for d in all_due if d.domain != "irl"]
    hints = []
    if non_critical_irl:
        hints.append(f"{len(non_critical_irl)} non-critical")
    if game:
        hints.append(f"{len(game)} game")

    if not critical and not hints:
        return None

    lines = ["=== DAILIES ==="]
    for d in critical:
        marker = " ⚠ overdue" if d.is_overdue(session) else ""
        lines.append(f"- #{d.id} {d.description}{marker}")
    if hints:
        lines.append(f"({'; '.join(hints)} also due today — kb daily list --all)")

    return "\n".join(lines)


def _other_contexts_hint(session: Session, in_scope_ids: set[int], all_pending_context_ids: list[Optional[int]]) -> str:
    """A one-line summary of how many items outside the current context filter are
    waiting elsewhere -- e.g. "3 other contexts have 7 pending items" -- without
    rendering their contents, so switching context stays a deliberate action."""
    outside = [cid for cid in all_pending_context_ids if cid is not None and cid not in in_scope_ids]
    if not outside:
        return ""
    other_context_count = len(set(outside))
    return f"({len(outside)} item(s) in {other_context_count} other context(s))"


def goals_section(session: Session, context: Optional[Context]) -> str | None:
    in_scope = Context.self_and_descendants(session, context.name) if context else None
    goals = Goal.active(session, contexts=in_scope, include_no_context=True)
    if not goals:
        return None
    lines = ["=== GOALS ==="]
    for g in goals:
        ctx = f" [{g.context.name}]" if g.context else ""
        lines.append(f"- #{g.id} {g.title}{ctx}")
    if context is not None:
        all_ids = [g.context_id for g in Goal.active(session)]
        hint = _other_contexts_hint(session, {c.id for c in in_scope} if in_scope else set(), all_ids)
        if hint:
            lines.append(hint)
    return "\n".join(lines)


def todos_section(session: Session, context: Optional[Context]) -> str | None:
    in_scope = Context.self_and_descendants(session, context.name) if context else None
    todos = Todo.active(session, contexts=in_scope, include_no_context=True)
    if not todos:
        return None
    lines = ["=== TODOS ==="]
    for t in todos:
        goal = f" → {t.goal.title}" if t.goal else ""
        ctx = f" [{t.context.name}]" if t.context else ""
        lines.append(f"- #{t.id} [{t.status.value}] {t.title}{goal}{ctx}")
    if context is not None:
        all_ids = [t.context_id for t in Todo.active(session)]
        hint = _other_contexts_hint(session, {c.id for c in in_scope} if in_scope else set(), all_ids)
        if hint:
            lines.append(hint)
    return "\n".join(lines)


def people_section(session: Session) -> str | None:
    overdue = Person.overdue_for_contact(session)
    if not overdue:
        return None
    lines = ["=== REACH OUT ==="]
    for p in overdue:
        last = p.last_contacted.strftime("%Y-%m-%d") if p.last_contacted else "never"
        lines.append(f"- {p.name} (last: {last}, every {p.reach_out_every_days}d)")
    return "\n".join(lines)


def wishlist_section(session: Session) -> str | None:
    pinned = Wishlist.top(session, 5, pinned_only=True)
    if not pinned:
        return None
    lines = ["=== WISHLIST (pinned) ==="]
    for w in pinned:
        price = ""
        if w.price_min is not None or w.price_max is not None:
            lo = f"${w.price_min}" if w.price_min is not None else ""
            hi = f"${w.price_max}" if w.price_max is not None else ""
            price = f" ({lo}–{hi})" if lo and hi else f" ({lo or hi})"
        rank = w.priority if w.priority is not None else w.score
        lines.append(f"- #{w.id} {w.title}{price} [{w.effort.value}] priority={rank}")
    return "\n".join(lines)


def inbox_section(session: Session) -> str | None:
    items = InboxItem.pending(session)
    if not items:
        return None
    by_category: dict[str, int] = {}
    for i in items:
        by_category.setdefault(i.category or "(uncategorized)", 0)
        by_category[i.category or "(uncategorized)"] += 1
    breakdown = ", ".join(f"{count} {cat}" for cat, count in sorted(by_category.items()))
    return f"=== INBOX ({len(items)}) ===\n{breakdown} — kb inbox pending [--category C]"


def idea_section(session: Session) -> str | None:
    count = len(Idea.active(session))
    if not count:
        return None
    return f"{count} idea(s) — kb idea list"


SECTION_NAMES: tuple[str, ...] = ("anki", "dailies", "goals", "todos", "people", "wishlist", "inbox", "idea")


# Every section is Callable[[Session], str | None] except goals/todos, which also need the
# resolved --context override (see cmd_summary) -- built as a closure over that context rather
# than widening every section's signature just for the two that use it.
def _sections(context: Optional[Context]) -> dict[str, Callable[[Session], str | None]]:
    return {
        "anki": anki_section,
        "dailies": dailies_section,
        "goals": lambda session: goals_section(session, context),
        "todos": lambda session: todos_section(session, context),
        "people": people_section,
        "wishlist": wishlist_section,
        "inbox": inbox_section,
        "idea": idea_section,
    }


SECTION_ALIASES: dict[str, str] = {
    "d": "dailies",
    "g": "goals",
    "t": "todos",
    "w": "wishlist",
    "i": "inbox",
}


def cmd_summary(args: argparse.Namespace) -> None:
    sections_map = _sections(args.context)
    requested = [SECTION_ALIASES.get(s, s) for s in args.section]
    unknown = [s for s in requested if s not in sections_map]
    if unknown:
        print(f"invalid section(s) {unknown}; choose from {', '.join(sections_map)}", file=sys.stderr)
        sys.exit(2)

    names = requested or list(sections_map)
    rendered = [sections_map[name](args.session) for name in names]
    sections = [s for s in rendered if s is not None]

    now = datetime.now()
    persisted_current = CurrentContext.get(args.session)
    if persisted_current is None:
        ctx_label = f"context: {args.context.name} (default, no context ever switched to)"
    elif args.context.id != persisted_current.id:
        ctx_label = f"context: {args.context.name} (override; persisted: {persisted_current.name})"
    else:
        ctx_label = f"context: {persisted_current.name}"
    print(f"{now.strftime('%Y-%m-%d %H:%M')} (week {now.isocalendar().week})")
    print(f"{ctx_label} — kb context switch NAME\n")

    if not sections:
        print("Nothing tracked yet.")
    else:
        print("\n\n".join(sections))


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "summary", aliases=["sum", "s"], help="Print an overview of active Goals/Todos/overdue contacts/wishlist"
    )
    parser.add_argument(
        "section",
        nargs="*",
        metavar="SECTION",
        help=f"Only show these sections ({'/'.join(SECTION_NAMES)}; single-letter aliases: d/g/t/w/i); default: all",
    )
    parser.set_defaults(func=cmd_summary)
