"""Vendor / Item / Purchase operations -- price and quantity history for anything
transactable, real or in-game (see models.py's Vendor/VendorItem/Purchase docstrings).

Three separate top-level nouns (`kb vendor`, `kb item`, `kb purchase`) rather than one
combined command, matching every other kb entity's own noun -- `add`/`list`/`search` per
noun, plus `kb purchase add` taking a vendor name + item name instead of raw ids so a
purchase can be recorded in one call without looking up VendorItem.id first.
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import IrlItem, Item, Purchase, Vendor, VendorItem
from kb_cli._util import apply_purge, apply_restore, apply_soft_delete, resolve_text_arg
from kb_cli.search import cmd_search_deprecated


def _get_or_create_vendor_item(session: Session, vendor: Vendor, item: Item, vendor_sku: str) -> VendorItem:
    vi = session.scalars(
        select(VendorItem).where(VendorItem.vendor_id == vendor.id, VendorItem.item_id == item.id)
    ).one_or_none()
    if vi is None:
        vi = VendorItem(vendor_id=vendor.id, item_id=item.id, vendor_sku=vendor_sku)
        session.add(vi)
        session.flush()
    return vi


def cmd_vendor_add(args: argparse.Namespace) -> None:
    vendor = Vendor(
        name=args.name,
        domain=args.domain,
        kind=args.kind,
        notes=resolve_text_arg(args.notes) if args.notes else args.notes,
    )
    vendor.reembed()
    args.session.add(vendor)
    args.session.commit()
    print(f"Added: {vendor}")


def cmd_vendor_list(args: argparse.Namespace) -> None:
    q = select(Vendor).where(Vendor.deleted_at.is_(None))
    if args.domain:
        q = q.where(Vendor.domain == args.domain)
    vendors = args.session.scalars(q.order_by(Vendor.name)).all()
    if not vendors:
        print("No vendors.")
        return
    for v in vendors:
        print(repr(v))


def cmd_vendor_delete(args: argparse.Namespace) -> None:
    vendor = apply_soft_delete(args.session, Vendor, args.id, "Vendor")
    args.session.commit()
    print(f"Vendor #{vendor.id} {vendor.name!r}: soft-deleted (restore with `kb vendor restore {vendor.id}`)")


def cmd_vendor_restore(args: argparse.Namespace) -> None:
    vendor = apply_restore(args.session, Vendor, args.id, "Vendor")
    args.session.commit()
    print(f"Vendor #{vendor.id} {vendor.name!r}: restored")


def cmd_vendor_purge(args: argparse.Namespace) -> None:
    vendor = apply_purge(args.session, Vendor, args.id, "Vendor", args.force_delete_links)
    args.session.commit()
    print(f"Vendor #{vendor.id} {vendor.name!r}: purged (irreversible)")


def cmd_item_add(args: argparse.Namespace) -> None:
    cls = IrlItem if args.game == "irl" else Item
    kwargs = dict(
        name=args.name, game=args.game, upc=args.upc, notes=resolve_text_arg(args.notes) if args.notes else args.notes
    )
    if cls is IrlItem:
        kwargs["brand"] = args.brand
        kwargs["size"] = args.size
    item = cls(**kwargs)
    item.reembed()
    args.session.add(item)
    args.session.commit()
    print(f"Added: {item}")


def cmd_item_list(args: argparse.Namespace) -> None:
    q = select(Item).where(Item.deleted_at.is_(None))
    if args.game:
        q = q.where(Item.game == args.game)
    items = args.session.scalars(q.order_by(Item.name)).all()
    if not items:
        print("No items.")
        return
    for i in items:
        print(repr(i))


def cmd_item_delete(args: argparse.Namespace) -> None:
    item = apply_soft_delete(args.session, Item, args.id, "Item")
    args.session.commit()
    print(f"Item #{item.id} {item.name!r}: soft-deleted (restore with `kb item restore {item.id}`)")


def cmd_item_restore(args: argparse.Namespace) -> None:
    item = apply_restore(args.session, Item, args.id, "Item")
    args.session.commit()
    print(f"Item #{item.id} {item.name!r}: restored")


def cmd_item_purge(args: argparse.Namespace) -> None:
    item = apply_purge(args.session, Item, args.id, "Item", args.force_delete_links)
    args.session.commit()
    print(f"Item #{item.id} {item.name!r}: purged (irreversible)")


def cmd_purchase_add(args: argparse.Namespace) -> None:
    session = args.session
    vendor = session.scalars(select(Vendor).where(Vendor.name == args.vendor)).one_or_none()
    if vendor is None:
        print(f"Vendor {args.vendor!r}: not found -- create it first with `kb vendor add`", file=sys.stderr)
        sys.exit(1)
    item = session.scalars(select(Item).where(Item.name == args.item)).one_or_none()
    if item is None:
        print(f"Item {args.item!r}: not found -- create it first with `kb item add`", file=sys.stderr)
        sys.exit(1)
    vendor_item = _get_or_create_vendor_item(session, vendor, item, args.sku or "")
    purchase = Purchase(
        vendor_item_id=vendor_item.id,
        quantity=args.quantity,
        unit_price=args.unit_price,
        total_price=args.total_price,
        notes=resolve_text_arg(args.notes) if args.notes else args.notes,
    )
    session.add(purchase)
    session.flush()
    purchase.reembed()
    session.commit()
    print(f"Added: {purchase}")


def cmd_purchase_list(args: argparse.Namespace) -> None:
    q = select(Purchase).where(Purchase.deleted_at.is_(None)).order_by(Purchase.purchased_at.desc())
    purchases = args.session.scalars(q).all()
    if args.vendor:
        purchases = [p for p in purchases if p.vendor_item.vendor.name == args.vendor]
    if args.item:
        purchases = [p for p in purchases if p.vendor_item.item.name == args.item]
    if not purchases:
        print("No purchases.")
        return
    for p in purchases:
        print(repr(p))


def cmd_purchase_delete(args: argparse.Namespace) -> None:
    purchase = apply_soft_delete(args.session, Purchase, args.id, "Purchase")
    args.session.commit()
    print(f"Purchase #{purchase.id}: soft-deleted (restore with `kb purchase restore {purchase.id}`)")


def cmd_purchase_restore(args: argparse.Namespace) -> None:
    purchase = apply_restore(args.session, Purchase, args.id, "Purchase")
    args.session.commit()
    print(f"Purchase #{purchase.id}: restored")


def cmd_purchase_purge(args: argparse.Namespace) -> None:
    purchase = apply_purge(args.session, Purchase, args.id, "Purchase", args.force_delete_links)
    args.session.commit()
    print(f"Purchase #{purchase.id}: purged (irreversible)")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    vendor_parser = subparsers.add_parser("vendor", help="Vendor operations (stores, NPCs, player shops, ...)")
    vsub = vendor_parser.add_subparsers(dest="cmd", required=True)

    v_add = vsub.add_parser("add", help="Add a vendor")
    v_add.add_argument("name")
    v_add.add_argument("--domain", default="irl", help="e.g. irl, pg")
    v_add.add_argument("--kind", help="e.g. grocery, npc, player_shop")
    v_add.add_argument("--notes")
    v_add.set_defaults(func=cmd_vendor_add)

    v_list = vsub.add_parser("list", help="List vendors")
    v_list.add_argument("--domain")
    v_list.set_defaults(func=cmd_vendor_list)

    v_search = vsub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    v_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    v_search.set_defaults(func=cmd_search_deprecated)

    v_delete = vsub.add_parser("delete", help="Soft-delete a vendor (reversible, see restore)")
    v_delete.add_argument("id", type=int)
    v_delete.set_defaults(func=cmd_vendor_delete)

    v_restore = vsub.add_parser("restore", help="Undo a soft delete on a vendor")
    v_restore.add_argument("id", type=int)
    v_restore.set_defaults(func=cmd_vendor_restore)

    v_purge = vsub.add_parser("purge", help="Permanently delete a vendor (irreversible)")
    v_purge.add_argument("id", type=int)
    v_purge.add_argument("--force-delete-links", action="store_true", help="Also delete any EntityLinks pointing at it")
    v_purge.set_defaults(func=cmd_vendor_purge)

    item_parser = subparsers.add_parser("item", help="Item operations (real-world and in-game)")
    isub = item_parser.add_subparsers(dest="cmd", required=True)

    i_add = isub.add_parser("add", help="Add an item")
    i_add.add_argument("name")
    i_add.add_argument("--game", default="irl", help="e.g. irl, pg")
    i_add.add_argument("--upc")
    i_add.add_argument("--brand", help="IrlItem only")
    i_add.add_argument("--size", help="IrlItem only, free text e.g. '5.5oz can'")
    i_add.add_argument("--notes")
    i_add.set_defaults(func=cmd_item_add)

    i_list = isub.add_parser("list", help="List items")
    i_list.add_argument("--game")
    i_list.set_defaults(func=cmd_item_list)

    i_search = isub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    i_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    i_search.set_defaults(func=cmd_search_deprecated)

    i_delete = isub.add_parser("delete", help="Soft-delete an item (reversible, see restore)")
    i_delete.add_argument("id", type=int)
    i_delete.set_defaults(func=cmd_item_delete)

    i_restore = isub.add_parser("restore", help="Undo a soft delete on an item")
    i_restore.add_argument("id", type=int)
    i_restore.set_defaults(func=cmd_item_restore)

    i_purge = isub.add_parser("purge", help="Permanently delete an item (irreversible)")
    i_purge.add_argument("id", type=int)
    i_purge.add_argument("--force-delete-links", action="store_true", help="Also delete any EntityLinks pointing at it")
    i_purge.set_defaults(func=cmd_item_purge)

    purchase_parser = subparsers.add_parser("purchase", help="Purchase operations (price/quantity history)")
    psub = purchase_parser.add_subparsers(dest="cmd", required=True)

    p_add = psub.add_parser("add", help="Record a purchase (vendor and item must already exist)")
    p_add.add_argument("vendor", help="Existing Vendor name")
    p_add.add_argument("item", help="Existing Item name")
    p_add.add_argument("--sku", help="Vendor's own SKU/code for this item, if known")
    p_add.add_argument("--quantity", type=float, default=1)
    p_add.add_argument("--unit-price", type=float)
    p_add.add_argument("--total-price", type=float)
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_purchase_add)

    p_list = psub.add_parser("list", help="List purchases, most recent first")
    p_list.add_argument("--vendor")
    p_list.add_argument("--item")
    p_list.set_defaults(func=cmd_purchase_list)

    p_search = psub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    p_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    p_search.set_defaults(func=cmd_search_deprecated)

    p_delete = psub.add_parser("delete", help="Soft-delete a purchase (reversible, see restore)")
    p_delete.add_argument("id", type=int)
    p_delete.set_defaults(func=cmd_purchase_delete)

    p_restore = psub.add_parser("restore", help="Undo a soft delete on a purchase")
    p_restore.add_argument("id", type=int)
    p_restore.set_defaults(func=cmd_purchase_restore)

    p_purge = psub.add_parser("purge", help="Permanently delete a purchase (irreversible)")
    p_purge.add_argument("id", type=int)
    p_purge.add_argument("--force-delete-links", action="store_true", help="Also delete any EntityLinks pointing at it")
    p_purge.set_defaults(func=cmd_purchase_purge)
