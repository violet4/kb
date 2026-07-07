"""Project Gorgon Quest operations."""

import argparse
import sys

from models_pg import PgNpc, PgQuest

from kb_cli._util import get_by_name


def cmd_show(args: argparse.Namespace) -> None:
    for i, quest_id in enumerate(args.ids):
        if i > 0:
            print()
        quest = args.session.get(PgQuest, quest_id)
        if quest is None:
            print(f"id: {quest_id}\nerror: not found", file=sys.stderr)
            continue
        print(f"id: {quest.id}")
        print(f"title: {quest.title}")
        print(f"status: {quest.status}")
        print(f"giver: {quest.giver.name}")
        if quest.completion_npc:
            print(f"completion_npc: {quest.completion_npc.name}")
        if quest.objectives:
            print(f"objectives: {quest.objectives}")
        if quest.rewards:
            print(f"rewards: {quest.rewards}")
        if quest.notes:
            print(f"notes: {quest.notes}")


def cmd_add(args: argparse.Namespace) -> None:
    giver = get_by_name(args.session, PgNpc, args.giver)
    completion = get_by_name(args.session, PgNpc, args.completion) if args.completion else None
    quest = PgQuest(
        title=args.title,
        giver_npc_id=giver.id,
        completion_npc_id=completion.id if completion else None,
        status=args.status,
        objectives=args.objectives,
        rewards=args.rewards,
        notes=args.notes or "",
    )
    args.session.add(quest)
    args.session.commit()
    print(f"Added: #{quest.id} {quest.title!r} [{quest.status}]")


def cmd_complete(args: argparse.Namespace) -> None:
    for quest_id in args.ids:
        quest = args.session.get(PgQuest, quest_id)
        if quest is None:
            print(f"Quest #{quest_id}: not found", file=sys.stderr)
            continue
        quest.status = "completed"
        print(f"Quest #{quest_id}: {quest.title!r} -> completed")
    args.session.commit()


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("quest", help="Project Gorgon Quest operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show Quest details")
    p_show.add_argument("ids", nargs="+", type=int)
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add", help="Add a Quest")
    p_add.add_argument("title")
    p_add.add_argument("--giver", required=True, help="Giver NPC name (must already exist)")
    p_add.add_argument("--completion", help="Completion NPC name, if different from giver")
    p_add.add_argument("--status", default="active", choices=["available", "active", "completed", "turned_in"])
    p_add.add_argument("--objectives")
    p_add.add_argument("--rewards")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_complete = sub.add_parser("complete", help="Mark Quest(s) completed")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)
