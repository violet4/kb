#!/usr/bin/env python3
"""Personal knowledge base REPL/runner."""
import argparse
import ast
import code
import sys

from sqlalchemy import select

from models import (
    Base, ChangeLog, Collection, Context, Goal, GoalStatus, Note, Person, PersonTier,
    Reference, Todo, TodoStatus, WishlistEffort, WishlistStatus, Wishlist,
    WorkingMemory, init_db, sess,
)

parser = argparse.ArgumentParser(description="KB runner")
parser.add_argument("command", nargs="?", help="Python expression to execute")
parser.add_argument("--no-commit", action="store_true", help="Skip auto-commit")
args = parser.parse_args()

ns = {
    "sess": sess,
    "select": select,
    "Collection": Collection,
    "Note": Note,
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
    tree = ast.parse(args.command)
    last_expr = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last_expr = ast.Expression(tree.body.pop().value)

    exec(compile(tree, "<kb>", "exec"), ns)  # noqa: S102
    if last_expr is not None:
        result = eval(compile(last_expr, "<kb>", "eval"), ns)  # noqa: S307
        if result is not None:
            print(repr(result))

    if not args.no_commit:
        sess.commit()
else:
    banner = "KB | All models and `sess` are pre-loaded. Changes are NOT auto-committed — call sess.commit() explicitly."
    code.interact(banner=banner, local=ns, exitmsg="")
