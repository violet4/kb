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
from kb_cli._util import resolve_text_arg
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
    q = select(Vendor)
    if args.domain:
        q = q.where(Vendor.domain == args.domain)
    vendors = args.session.scalars(q.order_by(Vendor.name)).all()
    if not vendors:
        print("No vendors.")
        return
    for v in vendors:
        print(repr(v))


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
    q = select(Item)
    if args.game:
        q = q.where(Item.game == args.game)
    items = args.session.scalars(q.order_by(Item.name)).all()
    if not items:
        print("No items.")
        return
    for i in items:
        print(repr(i))


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
    q = select(Purchase).order_by(Purchase.purchased_at.desc())
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
