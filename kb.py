#!/usr/bin/env -S uv run --project /home/violet/kb python3
"""Personal knowledge base REPL/runner."""
import argparse
import ast
import code
import sys

from sqlalchemy import select

from context import resolve_context
from models import (
    Base, ChangeLog, Collection, Context, CurrentContext, Daily, Goal, GoalStatus,
    InboxItem, IrlItem, Item, Journal, LogEntry, Note, Person, PersonTier, Purchase,
    Reference, Todo, TodoStatus, Vendor, VendorItem, WishlistEffort, WishlistStatus,
    Wishlist, WorkingMemory, init_db, sess,
)
from models_pg import PgDungeon, PgFriendlyPlayer, PgItem, PgNpc, PgNpcRace, PgNpcRelation, PgPlayer, PgQuest

parser = argparse.ArgumentParser(description="KB runner")
parser.add_argument("command", nargs="?", help="Python expression to execute")
parser.add_argument("-f", "--file", help="Read command from a script file instead of the command arg (auto-commits like inline commands)")
parser.add_argument("--no-commit", action="store_true", help="Skip auto-commit")
parser.add_argument(
    "-i", "--interactive", action="store_true",
    help="Start an interactive REPL. Changes are NOT auto-committed — call sess.commit() explicitly.",
)
parser.add_argument(
    "--context", metavar="NAME",
    help="Act in context NAME for this command only, without changing the persisted current context. "
         "Pre-loaded as `context` in the namespace.",
)
args = parser.parse_args()

if not args.command and not args.file and not args.interactive:
    parser.error("one of: command, -f/--file, or -i/--interactive is required")

if args.file:
    with open(args.file) as f:
        args.command = f.read()

ns = {
    "sess": sess,
    "select": select,
    "context": resolve_context(args.context),
    "Collection": Collection,
    "Note": Note,
    "ChangeLog": ChangeLog,
    "Context": Context,
    "CurrentContext": CurrentContext,
    "Daily": Daily,
    "Goal": Goal,
    "GoalStatus": GoalStatus,
    "InboxItem": InboxItem,
    "IrlItem": IrlItem,
    "Item": Item,
    "Journal": Journal,
    "LogEntry": LogEntry,
    "PgDungeon": PgDungeon,
    "PgFriendlyPlayer": PgFriendlyPlayer,
    "PgItem": PgItem,
    "PgNpc": PgNpc,
    "PgNpcRace": PgNpcRace,
    "PgNpcRelation": PgNpcRelation,
    "PgPlayer": PgPlayer,
    "PgQuest": PgQuest,
    "Person": Person,
    "PersonTier": PersonTier,
    "Purchase": Purchase,
    "Reference": Reference,
    "Todo": Todo,
    "TodoStatus": TodoStatus,
    "Vendor": Vendor,
    "VendorItem": VendorItem,
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

    exec_ran = False
    try:
        exec(compile(tree, "<kb>", "exec"), ns)  # noqa: S102
        exec_ran = True
        if last_expr is not None:
            result = eval(compile(last_expr, "<kb>", "eval"), ns)  # noqa: S307
            if result is not None:
                print(repr(result))
    except Exception:
        state = "ran but NOT committed (mutations may be visible only in-session)" if exec_ran else "did not run"
        print(f"kb.py: command raised; command {state}.", file=sys.stderr)
        raise

    if not args.no_commit:
        sess.commit()
else:
    banner = "KB interactive mode | All models and `sess` are pre-loaded. Changes are NOT auto-committed — call sess.commit() explicitly."
    code.interact(banner=banner, local=ns, exitmsg="")
