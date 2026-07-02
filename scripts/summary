#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Goal, Person, Todo, Wishlist, sess

goals = Goal.active()
todos = Todo.pending()
overdue = Person.overdue_for_contact()
top_wishes = Wishlist.top(5)

sections = []

if goals:
    lines = ["=== GOALS ==="]
    for g in goals:
        ctx = f" [{g.context.name}]" if g.context else ""
        note = f" | {g.notes}" if g.notes else ""
        lines.append(f"- {g.title}{ctx}{note}")
    sections.append("\n".join(lines))

if todos:
    lines = ["=== TODOS ==="]
    for t in todos:
        goal = f" → {t.goal.title}" if t.goal else ""
        ctx = f" [{t.context.name}]" if t.context else ""
        lines.append(f"- [{t.status.value}] {t.title}{goal}{ctx}")
    sections.append("\n".join(lines))

if overdue:
    lines = ["=== REACH OUT ==="]
    for p in overdue:
        last = p.last_contacted.strftime("%Y-%m-%d") if p.last_contacted else "never"
        lines.append(f"- {p.name} (last: {last}, every {p.reach_out_every_days}d)")
    sections.append("\n".join(lines))

if top_wishes:
    lines = ["=== WISHLIST (top 5) ==="]
    for w in top_wishes:
        price = ""
        if w.price_min is not None or w.price_max is not None:
            lo = f"${w.price_min}" if w.price_min is not None else ""
            hi = f"${w.price_max}" if w.price_max is not None else ""
            price = f" ({lo}–{hi})" if lo and hi else f" ({lo or hi})"
        rank = w.priority if w.priority is not None else w.score
        lines.append(f"- {w.title}{price} [{w.effort.value}] priority={rank}")
    sections.append("\n".join(lines))

if not sections:
    print("Nothing tracked yet.")
else:
    print("\n\n".join(sections))

sess.close()
