"""Print an overview of active Goals/Todos/overdue contacts/wishlist/inbox."""
import sys
from datetime import datetime

from models import Goal, InboxItem, Person, Todo, Wishlist


def goals_section():
    goals = Goal.active()
    if not goals:
        return None
    lines = ["=== GOALS ==="]
    for g in goals:
        ctx = f" [{g.context.name}]" if g.context else ""
        lines.append(f"- #{g.id} {g.title}{ctx}")
    return "\n".join(lines)


def todos_section():
    todos = Todo.pending()
    if not todos:
        return None
    lines = ["=== TODOS ==="]
    for t in todos:
        goal = f" → {t.goal.title}" if t.goal else ""
        ctx = f" [{t.context.name}]" if t.context else ""
        lines.append(f"- #{t.id} [{t.status.value}] {t.title}{goal}{ctx}")
    return "\n".join(lines)


def people_section():
    overdue = Person.overdue_for_contact()
    if not overdue:
        return None
    lines = ["=== REACH OUT ==="]
    for p in overdue:
        last = p.last_contacted.strftime("%Y-%m-%d") if p.last_contacted else "never"
        lines.append(f"- {p.name} (last: {last}, every {p.reach_out_every_days}d)")
    return "\n".join(lines)


def wishlist_section():
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


def inbox_section():
    items = InboxItem.pending()
    if not items:
        return None
    lines = ["=== INBOX ==="]
    for i in items:
        source = f" [{i.source}]" if i.source else ""
        lines.append(f"- #{i.id}{source} {i.body[:80]}")
    return "\n".join(lines)


SECTIONS = {
    "goals": goals_section,
    "todos": todos_section,
    "people": people_section,
    "wishlist": wishlist_section,
    "inbox": inbox_section,
}


def cmd_summary(args):
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


def add_subparser(subparsers):
    parser = subparsers.add_parser("summary", help="Print an overview of active Goals/Todos/overdue contacts/wishlist")
    parser.add_argument("section", nargs="*", metavar="SECTION",
                         help=f"Only show these sections ({'/'.join(SECTIONS)}); default: all")
    parser.set_defaults(func=cmd_summary)
