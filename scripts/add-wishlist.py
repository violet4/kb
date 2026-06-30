#!/usr/bin/env python3
"""Interactively add a wishlist item."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Wishlist, WishlistEffort, WishlistStatus, sess


def prompt(label, default=None, choices=None):
    hint = f" [{default}]" if default is not None else ""
    if choices:
        hint += f" ({'/'.join(choices)})"
    value = input(f"{label}{hint}: ").strip()
    return value or (str(default) if default is not None else None)


def prompt_int(label, default):
    while True:
        raw = prompt(label, default=default)
        try:
            v = int(raw)
            if 0 <= v <= 100:
                return v
            print("  Must be 0–100.")
        except (TypeError, ValueError):
            print("  Enter a number 0–100.")


def prompt_price(label):
    raw = prompt(label, default="")
    if not raw:
        return None
    try:
        return float(raw.lstrip("$"))
    except ValueError:
        print(f"  Skipping {label} (invalid).")
        return None


effort_choices = [e.value for e in WishlistEffort]

print("=== Add Wishlist Item ===\n")

title = prompt("Title")
if not title:
    print("Title is required.")
    sys.exit(1)

description = prompt("Description")
price_min = prompt_price("Price min ($)")
price_max = prompt_price("Price max ($)")
importance = prompt_int("Importance", 50)
urgency = prompt_int("Urgency", 50)
clarity = prompt_int("Clarity", 50)

effort_raw = prompt("Effort", default="grab", choices=effort_choices)
try:
    effort = WishlistEffort(effort_raw)
except ValueError:
    print(f"  Invalid effort '{effort_raw}', defaulting to 'grab'.")
    effort = WishlistEffort.GRAB

notes = prompt("Notes")

item = Wishlist(
    title=title,
    description=description or None,
    price_min=price_min,
    price_max=price_max,
    importance=importance,
    urgency=urgency,
    clarity=clarity,
    effort=effort,
    notes=notes or None,
)
sess.add(item)
sess.commit()

print(f"\nAdded: {item}")
