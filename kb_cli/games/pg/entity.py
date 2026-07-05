"""Project Gorgon entity operations: npc, mob, mob-drop, item, player, character, relation."""
from sqlalchemy import select

from models import sess
from models_pg import PgCharacter, PgItem, PgMob, PgMobDrop, PgNpc, PgNpcRelation, PgPlayer

from kb_cli._util import get_by_name, print_fields


# --- npc ---

def cmd_npc_show(args):
    npc = get_by_name(sess, PgNpc, args.name)
    print_fields([
        ("id", npc.id),
        ("name", npc.name),
        ("race", npc.race.name if npc.race else None),
        ("location", npc.location),
        ("notes", npc.notes),
    ])


def cmd_npc_add(args):
    npc = PgNpc(name=args.name, location=args.location, notes=args.notes or "")
    sess.add(npc)
    sess.commit()
    print(npc)


def cmd_npc_update(args):
    npc = get_by_name(sess, PgNpc, args.name)
    if args.location is not None:
        npc.location = args.location
    if args.notes is not None:
        npc.notes = args.notes
    sess.commit()
    print(npc)


# --- mob ---

def cmd_mob_show(args):
    mob = get_by_name(sess, PgMob, args.name)
    print_fields([
        ("name", mob.name),
        ("location", mob.location),
        ("notes", mob.notes),
    ])


def cmd_mob_add(args):
    mob = PgMob(name=args.name, location=args.location, notes=args.notes or "")
    sess.add(mob)
    sess.commit()
    print(mob)


def cmd_mob_update(args):
    mob = get_by_name(sess, PgMob, args.name)
    if args.location is not None:
        mob.location = args.location
    if args.notes is not None:
        mob.notes = args.notes
    sess.commit()
    print(mob)


def cmd_mob_search(args):
    q = select(PgMob).where(
        PgMob.name.ilike(f"%{args.query}%") | PgMob.location.ilike(f"%{args.query}%")
    )
    mobs = sess.scalars(q).all()
    if not mobs:
        print(f"No mobs matching {args.query!r}.")
        return
    for mob in mobs:
        print(mob)
        if args.loot:
            drops = sess.scalars(select(PgMobDrop).where(PgMobDrop.mob_id == mob.id)).all()
            for d in drops:
                print(f"  {d}")


# --- mob-drop ---

def cmd_mob_drop_add(args):
    mob = get_by_name(sess, PgMob, args.mob)
    item = get_by_name(sess, PgItem, args.item)
    drop = PgMobDrop(mob_id=mob.id, item_id=item.id, notes=args.notes or "")
    sess.add(drop)
    sess.commit()
    print(drop)


def cmd_mob_drop_show(args):
    mob = get_by_name(sess, PgMob, args.mob)
    drops = sess.scalars(select(PgMobDrop).where(PgMobDrop.mob_id == mob.id)).all()
    if not drops:
        print(f"No known drops for {mob.name!r}.")
        return
    for d in drops:
        print(d)


# --- item ---

def cmd_item_show(args):
    item = get_by_name(sess, PgItem, args.name)
    print_fields([
        ("id", item.id),
        ("name", item.name),
        ("kind", item.kind),
        ("sources", item.sources),
        ("notes", item.notes),
    ])


def cmd_item_search(args):
    items = sess.scalars(select(PgItem).where(PgItem.name.ilike(f"%{args.query}%"))).all()
    if not items:
        print(f"No items matching {args.query!r}.")
        return
    for item in items:
        print(item)
        if args.mobs:
            drops = sess.scalars(select(PgMobDrop).where(PgMobDrop.item_id == item.id)).all()
            for d in drops:
                print(f"  {d}")


# --- player ---

def cmd_player_show(args):
    player = get_by_name(sess, PgPlayer, args.name)
    print_fields([
        ("name", player.name),
        ("friendly", player.friendly),
        ("notes", player.notes),
    ])


def cmd_player_add(args):
    player = PgPlayer(name=args.name, friendly=not args.unfriendly, notes=args.notes or "")
    sess.add(player)
    sess.commit()
    print(player)


def cmd_player_update(args):
    player = get_by_name(sess, PgPlayer, args.name)
    if args.friendly is not None:
        player.friendly = args.friendly
    if args.notes is not None:
        player.notes = args.notes
    sess.commit()
    print(player)


# --- character ---

def cmd_character_show(args):
    character = get_by_name(sess, PgCharacter, args.name)
    print_fields([
        ("name", character.name),
        ("race", character.race),
        ("is_druid", character.is_druid),
        ("is_vampire", character.is_vampire),
        ("notes", character.notes),
    ])


def cmd_character_update(args):
    character = get_by_name(sess, PgCharacter, args.name)
    if args.race is not None:
        character.race = args.race
    if args.druid is not None:
        character.is_druid = args.druid
    if args.vampire is not None:
        character.is_vampire = args.vampire
    if args.notes is not None:
        character.notes = args.notes
    sess.commit()
    print(character)


# --- relation ---

def cmd_relation_add(args):
    character = get_by_name(sess, PgCharacter, args.character)
    npc = get_by_name(sess, PgNpc, args.npc)
    relation = PgNpcRelation(character_id=character.id, npc_id=npc.id, favor=args.favor, notes=args.notes or "")
    sess.add(relation)
    sess.commit()
    print(relation)


def cmd_relation_show(args):
    character = get_by_name(sess, PgCharacter, args.character)
    relations = sess.scalars(select(PgNpcRelation).where(PgNpcRelation.character_id == character.id)).all()
    if not relations:
        print(f"No known NPC relations for {character.name!r}.")
        return
    for r in relations:
        print(r)


def add_subparser(subparsers):
    parser = subparsers.add_parser("entity", help="Project Gorgon entity operations")
    sub = parser.add_subparsers(dest="entity", required=True)

    p_npc = sub.add_parser("npc", help="NPC operations (interactable: trainer/shop/quest-giver/lore)")
    npc_sub = p_npc.add_subparsers(dest="cmd", required=True)
    p = npc_sub.add_parser("show"); p.add_argument("name"); p.set_defaults(func=cmd_npc_show)
    p = npc_sub.add_parser("add"); p.add_argument("name"); p.add_argument("--location"); p.add_argument("--notes"); p.set_defaults(func=cmd_npc_add)
    p = npc_sub.add_parser("update"); p.add_argument("name"); p.add_argument("--location"); p.add_argument("--notes"); p.set_defaults(func=cmd_npc_update)

    p_mob = sub.add_parser("mob", help="Mob operations (killable enemies)")
    mob_sub = p_mob.add_subparsers(dest="cmd", required=True)
    p = mob_sub.add_parser("show"); p.add_argument("name"); p.set_defaults(func=cmd_mob_show)
    p = mob_sub.add_parser("add"); p.add_argument("name"); p.add_argument("--location"); p.add_argument("--notes"); p.set_defaults(func=cmd_mob_add)
    p = mob_sub.add_parser("update"); p.add_argument("name"); p.add_argument("--location"); p.add_argument("--notes"); p.set_defaults(func=cmd_mob_update)
    p = mob_sub.add_parser("search", help="Search mobs by name/location substring")
    p.add_argument("query")
    p.add_argument("--loot", action="store_true", help="Also show each match's known drops")
    p.set_defaults(func=cmd_mob_search)

    p_drop = sub.add_parser("mob-drop", help="Mob -> item drop relationships")
    drop_sub = p_drop.add_subparsers(dest="cmd", required=True)
    p = drop_sub.add_parser("add"); p.add_argument("mob"); p.add_argument("item"); p.add_argument("--notes"); p.set_defaults(func=cmd_mob_drop_add)
    p = drop_sub.add_parser("show"); p.add_argument("mob"); p.set_defaults(func=cmd_mob_drop_show)

    p_item = sub.add_parser("item", help="PG item lookups")
    item_sub = p_item.add_subparsers(dest="cmd", required=True)
    p = item_sub.add_parser("show"); p.add_argument("name"); p.set_defaults(func=cmd_item_show)
    p = item_sub.add_parser("search", help="Search items by name substring")
    p.add_argument("query")
    p.add_argument("--mobs", action="store_true", help="Also show which mobs drop each match")
    p.set_defaults(func=cmd_item_search)

    p_player = sub.add_parser("player", help="Other players' characters you've encountered")
    player_sub = p_player.add_subparsers(dest="cmd", required=True)
    p = player_sub.add_parser("show"); p.add_argument("name"); p.set_defaults(func=cmd_player_show)
    p = player_sub.add_parser("add"); p.add_argument("name"); p.add_argument("--unfriendly", action="store_true"); p.add_argument("--notes"); p.set_defaults(func=cmd_player_add)
    p = player_sub.add_parser("update"); p.add_argument("name")
    p.add_argument("--friendly", dest="friendly", action="store_true", default=None)
    p.add_argument("--unfriendly", dest="friendly", action="store_false")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_player_update)

    p_character = sub.add_parser("character", help="Your own character(s)")
    character_sub = p_character.add_subparsers(dest="cmd", required=True)
    p = character_sub.add_parser("show"); p.add_argument("name"); p.set_defaults(func=cmd_character_show)
    p = character_sub.add_parser("update"); p.add_argument("name")
    p.add_argument("--race")
    p.add_argument("--druid", dest="druid", action="store_true", default=None)
    p.add_argument("--no-druid", dest="druid", action="store_false")
    p.add_argument("--vampire", dest="vampire", action="store_true", default=None)
    p.add_argument("--no-vampire", dest="vampire", action="store_false")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_character_update)

    p_relation = sub.add_parser("relation", help="Your character's favor/standing with an NPC")
    relation_sub = p_relation.add_subparsers(dest="cmd", required=True)
    p = relation_sub.add_parser("add"); p.add_argument("character"); p.add_argument("npc"); p.add_argument("favor"); p.add_argument("--notes"); p.set_defaults(func=cmd_relation_add)
    p = relation_sub.add_parser("show"); p.add_argument("character"); p.set_defaults(func=cmd_relation_show)
