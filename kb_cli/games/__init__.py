"""Per-game command groups (pg, and future games)."""
import argparse

from kb_cli.games import pg


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("games", help="Per-game commands")
    sub = parser.add_subparsers(dest="game", required=True)
    pg.add_subparser(sub)
