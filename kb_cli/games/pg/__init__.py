"""Project Gorgon command group."""

import argparse

from kb_cli.games.pg import entity, quest


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("pg", help="Project Gorgon")
    sub = parser.add_subparsers(dest="pg_cmd", required=True)
    entity.add_subparser(sub)
    quest.add_subparser(sub)
