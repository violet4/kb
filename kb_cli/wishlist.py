"""Wishlist operations."""

import argparse
import sys
from typing import Iterable

from models import Wishlist, WishlistEffort, WishlistStatus


def _validate_0_100(args: argparse.Namespace, names: Iterable[str]) -> None:
    for name in names:
        value = getattr(args, name)
        if value is not None and not 0 <= value <= 100:
            print(f"--{name} must be 0-100, got {value}", file=sys.stderr)
            sys.exit(2)


def cmd_add(args: argparse.Namespace) -> None:
    _validate_0_100(args, ("importance", "urgency", "clarity"))
    item = Wishlist(
        title=args.title,
        description=args.description,
        price_min=args.price_min,
        price_max=args.price_max,
        importance=args.importance,
        urgency=args.urgency,
        clarity=args.clarity,
        effort=WishlistEffort(args.effort),
        priority=args.priority,
        notes=args.notes,
        pinned=args.pinned,
    )
    args.session.add(item)
    args.session.commit()
    print(f"Added: {item} score={item.score}")


def cmd_update(args: argparse.Namespace) -> None:
    _validate_0_100(args, ("importance", "urgency", "clarity"))
    item = args.session.get(Wishlist, args.id)
    if item is None:
        print(f"Wishlist #{args.id}: not found", file=sys.stderr)
        sys.exit(1)

    if args.title is not None:
        item.title = args.title
    if args.description is not None:
        item.description = args.description
    if args.price_min is not None:
        item.price_min = args.price_min
    if args.price_max is not None:
        item.price_max = args.price_max
    if args.importance is not None:
        item.importance = args.importance
    if args.urgency is not None:
        item.urgency = args.urgency
    if args.clarity is not None:
        item.clarity = args.clarity
    if args.effort is not None:
        item.effort = WishlistEffort(args.effort)
    if args.priority is not None:
        item.priority = args.priority
    if args.status is not None:
        item.status = WishlistStatus(args.status)
    if args.notes is not None:
        item.notes = args.notes
    if args.pinned is not None:
        item.pinned = args.pinned

    args.session.commit()
    print(f"Updated: {item} score={item.score}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("wishlist", help="Wishlist operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a wishlist item")
    p_add.add_argument("title")
    p_add.add_argument("--description")
    p_add.add_argument("--price-min", type=float)
    p_add.add_argument("--price-max", type=float)
    p_add.add_argument("--importance", type=int, default=50, help="0-100, default 50")
    p_add.add_argument("--urgency", type=int, default=50, help="0-100, default 50")
    p_add.add_argument("--clarity", type=int, default=50, help="0-100, default 50")
    p_add.add_argument("--effort", choices=[e.value for e in WishlistEffort], default="grab")
    p_add.add_argument("--priority", type=int, help="Explicit priority override (beats computed score)")
    p_add.add_argument("--notes")
    p_add.add_argument("--pinned", action="store_true", help="Show in kb summary")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing wishlist item")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--title")
    p_update.add_argument("--description")
    p_update.add_argument("--price-min", type=float)
    p_update.add_argument("--price-max", type=float)
    p_update.add_argument("--importance", type=int, help="0-100")
    p_update.add_argument("--urgency", type=int, help="0-100")
    p_update.add_argument("--clarity", type=int, help="0-100")
    p_update.add_argument("--effort", choices=[e.value for e in WishlistEffort])
    p_update.add_argument("--priority", type=int, help="Explicit priority override (beats computed score)")
    p_update.add_argument("--status", choices=[s.value for s in WishlistStatus])
    p_update.add_argument("--notes")
    pin_group = p_update.add_mutually_exclusive_group()
    pin_group.add_argument("--pinned", dest="pinned", action="store_true", default=None, help="Show in kb summary")
    pin_group.add_argument("--unpinned", dest="pinned", action="store_false", help="Hide from kb summary")
    p_update.set_defaults(func=cmd_update)
