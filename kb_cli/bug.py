"""`kb bug` -- `kb todo` with kind=bug baked in (see TodoKind's docstring in
models.py). Same table, same lifecycle/status/context machinery as Todo; this
module only builds the CLI tree with the --kind flag replaced by a fixed
TodoKind.BUG, via todo.add_subparser's locked_kind parameter -- there is no
separate Bug model, matching Redmine/Jira's "one issue table, a tracker/type
field distinguishes bug from task" shape rather than a parallel table."""

import argparse

from models import TodoKind

from kb_cli import todo


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    todo.add_subparser(subparsers, name="bug", aliases=[], help_prefix="Bug", locked_kind=TodoKind.BUG)
