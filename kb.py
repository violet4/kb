#!/usr/bin/env python3
"""Personal knowledge base REPL/runner."""
import argparse
import code
import sys

from models import (
    Base, ChangeLog, Context, Goal, GoalStatus, Person, PersonTier,
    Reference, Todo, TodoStatus, WishlistEffort, WishlistStatus, Wishlist,
    WorkingMemory, init_db, sess,
)

parser = argparse.ArgumentParser(description="KB runner")
parser.add_argument("command", nargs="?", help="Python expression to execute")
parser.add_argument("--no-commit", action="store_true", help="Skip auto-commit")
args = parser.parse_args()

ns = {
    "sess": sess,
    "ChangeLog": ChangeLog,
    "Context": Context,
    "Goal": Goal,
    "GoalStatus": GoalStatus,
    "Person": Person,
    "PersonTier": PersonTier,
    "Reference": Reference,
    "Todo": Todo,
    "TodoStatus": TodoStatus,
    "Wishlist": Wishlist,
    "WishlistEffort": WishlistEffort,
    "WishlistStatus": WishlistStatus,
    "WorkingMemory": WorkingMemory,
}

if args.command:
    exec(args.command, ns)  # noqa: S102
    if not args.no_commit:
        sess.commit()
else:
    banner = "KB | All models and `sess` are pre-loaded. Changes are NOT auto-committed — call sess.commit() explicitly."
    code.interact(banner=banner, local=ns, exitmsg="")
