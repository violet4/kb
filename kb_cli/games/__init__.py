"""Per-game command groups (pg, and future games)."""
from kb_cli.games import pg


def add_subparser(subparsers):
    parser = subparsers.add_parser("games", help="Per-game commands")
    sub = parser.add_subparsers(dest="game", required=True)
    pg.add_subparser(sub)
