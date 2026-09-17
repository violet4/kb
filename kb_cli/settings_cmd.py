"""General Settings fields not already owned by a more specific CLI module (notifications
volume/mute lives in kb_cli/notifications.py, archivebox_host in kb_cli/archivebox.py --
follow that same "each settings field's CLI lives next to its actual feature" precedent when
a new Settings field needs a command; add it here only when no more specific module fits)."""

import argparse

from models import Settings


def cmd_hard_delete(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    settings.hard_delete_enabled = args.value == "on"
    args.session.commit()
    state = "enabled" if settings.hard_delete_enabled else "disabled"
    print(f"Hard delete (purge) {state}. Soft delete/restore are unaffected.")


def cmd_show(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    print(f"hard_delete_enabled: {settings.hard_delete_enabled}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("settings", help="General kb settings")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show current settings")
    p_show.set_defaults(func=cmd_show)

    p_hard_delete = sub.add_parser(
        "hard-delete", help="Enable/disable `purge` (irreversible delete) across every entity"
    )
    p_hard_delete.add_argument("value", choices=["on", "off"])
    p_hard_delete.set_defaults(func=cmd_hard_delete)
