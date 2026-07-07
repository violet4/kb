"""Print an overview of active Goals/Todos/overdue contacts/wishlist/inbox."""
import argparse
import sys
from datetime import datetime
from typing import Callable

from models import Daily, DailyTier, Goal, InboxItem, Person, Todo, Wishlist


def anki_section() -> str | None:
    try:
        from anki.collection import Collection  # type: ignore[import-not-found]  # no stubs published
    except ImportError:
        return None

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


def dailies_section() -> str | None:
    critical = Daily.due(domain="irl", tier=DailyTier.CRITICAL)
    lines = []
    if critical:
        lines.append("=== DAILIES ===")
        for d in critical:
            lines.append(f"- #{d.id} {d.description}")

    all_due = Daily.due()
    non_critical_irl = [d for d in all_due if d.domain == "irl" and d.tier != DailyTier.CRITICAL]
    game = [d for d in all_due if d.domain != "irl"]
    hints = []
    if non_critical_irl:
        hints.append(f"{len(non_critical_irl)} non-critical")
    if game:
        hints.append(f"{len(game)} game")
    if hints:
        lines.append(f"({'; '.join(hints)} also due today — kb daily list --all)")

    return "\n".join(lines) if lines else None


def goals_section() -> str | None:
    goals = Goal.active()
    if not goals:
        return None
    lines = ["=== GOALS ==="]
    for g in goals:
        ctx = f" [{g.context.name}]" if g.context else ""
        lines.append(f"- #{g.id} {g.title}{ctx}")
    return "\n".join(lines)


def todos_section() -> str | None:
    todos = Todo.pending()
    if not todos:
        return None
    lines = ["=== TODOS ==="]
    for t in todos:
        goal = f" → {t.goal.title}" if t.goal else ""
        ctx = f" [{t.context.name}]" if t.context else ""
        lines.append(f"- #{t.id} [{t.status.value}] {t.title}{goal}{ctx}")
    return "\n".join(lines)


def people_section() -> str | None:
    overdue = Person.overdue_for_contact()
    if not overdue:
        return None
    lines = ["=== REACH OUT ==="]
    for p in overdue:
        last = p.last_contacted.strftime("%Y-%m-%d") if p.last_contacted else "never"
        lines.append(f"- {p.name} (last: {last}, every {p.reach_out_every_days}d)")
    return "\n".join(lines)


def wishlist_section() -> str | None:
    top_wishes = Wishlist.top(5)
    if not top_wishes:
        return None
    lines = ["=== WISHLIST (top 5) ==="]
    for w in top_wishes:
        price = ""
        if w.price_min is not None or w.price_max is not None:
            lo = f"${w.price_min}" if w.price_min is not None else ""
            hi = f"${w.price_max}" if w.price_max is not None else ""
            price = f" ({lo}–{hi})" if lo and hi else f" ({lo or hi})"
        rank = w.priority if w.priority is not None else w.score
        lines.append(f"- {w.title}{price} [{w.effort.value}] priority={rank}")
    return "\n".join(lines)


def inbox_section() -> str | None:
    items = InboxItem.pending()
    if not items:
        return None
    by_category: dict[str, int] = {}
    for i in items:
        by_category.setdefault(i.category or "(uncategorized)", 0)
        by_category[i.category or "(uncategorized)"] += 1
    breakdown = ", ".join(f"{count} {cat}" for cat, count in sorted(by_category.items()))
    return f"=== INBOX ({len(items)}) ===\n{breakdown} — kb inbox pending [--category C]"


SECTIONS: dict[str, Callable[[], str | None]] = {
    "anki": anki_section,
    "dailies": dailies_section,
    "goals": goals_section,
    "todos": todos_section,
    "people": people_section,
    "wishlist": wishlist_section,
    "inbox": inbox_section,
}


def cmd_summary(args: argparse.Namespace) -> None:
    unknown = [s for s in args.section if s not in SECTIONS]
    if unknown:
        print(f"invalid section(s) {unknown}; choose from {', '.join(SECTIONS)}", file=sys.stderr)
        sys.exit(2)

    names = args.section or list(SECTIONS)
    rendered = [SECTIONS[name]() for name in names]
    sections = [s for s in rendered if s is not None]

    now = datetime.now()
    print(f"{now.strftime('%Y-%m-%d %H:%M')} (week {now.isocalendar().week})\n")

    if not sections:
        print("Nothing tracked yet.")
    else:
        print("\n\n".join(sections))


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("summary", help="Print an overview of active Goals/Todos/overdue contacts/wishlist")
    parser.add_argument("section", nargs="*", metavar="SECTION",
                         help=f"Only show these sections ({'/'.join(SECTIONS)}); default: all")
    parser.set_defaults(func=cmd_summary)
