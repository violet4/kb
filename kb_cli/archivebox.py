"""kb ab: local capture (ArchivedLink) plus a push to the live ArchiveBox instance, queued on
kb.service's own background task so `kb ab add` returns immediately instead of blocking on
ArchiveBox's ~15-20s synchronous add (see kb Note #105) -- see ArchivedLink's docstring in
models.py, and kb Todo #70 for the fuller history.

kb owns auth end-to-end: credentials live in the OS keyring (kb_cli.secrets), never in
archivebox_compat's own env-var path, and the ArchiveBox hostname lives in Settings, never
baked into a URL anywhere -- see archivebox_url() below, the one place a host becomes a URL.

resolve_or_push() is the one function that actually talks to ArchiveBox, shared by the
server's background task (api/archivebox_router.py), startup reconciliation (server.py's
lifespan), and `kb ab retry` -- every caller gets the same dedup-before-push behavior and the
same push_status/resolved_at bookkeeping, so there's exactly one place that can decide a push
succeeded, failed, or found an existing snapshot."""

import argparse
import sys
import time
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from archivebox_compat import ArchiveBoxConfig, ArchiveBoxConfigError, Snapshot, get_client
from base import _now
from kb_cli.text import extract_paragraphs
from kb_cli.secrets import CredentialUnavailableError, get_credential, set_credential
from models import ArchivedLink, ArchivedLinkPushStatus, Settings

_CREDENTIAL_SERVICE = "kb-archivebox"
_SERVER_BASE_URL = "http://127.0.0.1:25690"
_WATCH_STATUS_INTERVAL_DEFAULT = 30


def archivebox_url(session: Session, path: str = "") -> str:
    """The one place Settings.archivebox_host becomes a real URL -- every command that prints
    or fetches a live ArchiveBox link goes through this, so a future hostname change is a
    one-row Settings edit, never a grep-and-replace."""
    settings = Settings.get(session)
    if not settings.archivebox_host:
        raise ArchiveBoxConfigError("ArchiveBox host not configured -- set with `kb ab configure --host HOST`")
    return f"https://{settings.archivebox_host}/{path.lstrip('/')}"


def _load_config(session: Session) -> ArchiveBoxConfig:
    settings = Settings.get(session)
    if not settings.archivebox_host:
        raise ArchiveBoxConfigError("ArchiveBox host not configured -- set with `kb ab configure --host HOST`")
    credential = get_credential(_CREDENTIAL_SERVICE)
    if credential is None:
        raise ArchiveBoxConfigError(
            "ArchiveBox credentials not configured -- set with `kb ab configure --set-credentials`"
        )
    username, password = credential
    return ArchiveBoxConfig(base_url=f"https://{settings.archivebox_host}", username=username, password=password)


def cmd_configure(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    did_something = False
    if args.host:
        settings.archivebox_host = args.host
        args.session.commit()
        print(f"ArchiveBox host set to {args.host}")
        did_something = True
    if args.set_credentials:
        import getpass

        username = input("ArchiveBox username (must be a Django staff account): ").strip()
        password = getpass.getpass("ArchiveBox password: ")
        if not username or not password:
            print("configure: username and password are both required, nothing stored", file=sys.stderr)
            sys.exit(1)
        set_credential(_CREDENTIAL_SERVICE, username, password)
        print("ArchiveBox credentials stored in OS keyring.")
        did_something = True
    if not did_something:
        print("Nothing to do -- pass --host and/or --set-credentials.", file=sys.stderr)
        sys.exit(1)


def resolve_or_push(session: Session, link: ArchivedLink) -> None:
    """Resolve link's ArchiveBox fate: check whether the URL is already archived (covers a push
    that actually succeeded server-side but whose result kb never recorded, e.g. a kb.service
    crash mid-push) before ever issuing a new add() -- so a retry is always safe to re-run, never
    a risk of double-submitting the same URL. Always ends with push_status set to SUCCESS or
    FAILED and resolved_at stamped; never leaves a row at PENDING/QUEUED. The one function every
    push path (cmd_add's background job, `kb ab retry`, startup reconciliation) calls."""
    try:
        config = _load_config(session)
        client = get_client(config)
        existing = [s for s in client.list(search=link.url) if s.url == link.url]
    except (ArchiveBoxConfigError, CredentialUnavailableError) as exc:
        link.push_error = str(exc)
        link.push_status = ArchivedLinkPushStatus.FAILED
        link.resolved_at = _now()
        session.commit()
        return

    if existing:
        snapshot = existing[0]
        link.ab_id = snapshot.id
        link.push_error = None
        link.push_status = ArchivedLinkPushStatus.SUCCESS
        link.resolved_at = _now()
        link.migrated_at = link.migrated_at or _now()
        session.commit()
        return

    try:
        snapshot = client.add(link.url)
    except Exception as exc:  # archivebox_compat backends raise plain RuntimeError/httpx errors
        link.push_error = str(exc)
        link.push_status = ArchivedLinkPushStatus.FAILED
        link.resolved_at = _now()
        session.commit()
        return

    link.ab_id = snapshot.id
    link.push_error = None
    link.push_status = ArchivedLinkPushStatus.SUCCESS
    link.resolved_at = _now()
    link.migrated_at = link.migrated_at or _now()
    session.commit()


def _report_already_saved(session: Session, existing: ArchivedLink) -> None:
    print(f"AB{existing.id}: already saved -- {existing.url}")
    print(existing)
    print(f"title: {existing.title!r}")
    print(f"reason: {existing.reason!r}")
    print(f"push_status: {existing.push_status.value}")
    if existing.ab_id:
        try:
            print(f"ab_url: {archivebox_url(session, f'archive/{existing.ab_id}/')}")
        except ArchiveBoxConfigError as exc:
            print(f"ab_url: unavailable -- {exc}", file=sys.stderr)
    print(f"Not creating a duplicate -- see `kb ab show {existing.id}`")


def cmd_add(args: argparse.Namespace) -> None:
    existing = ArchivedLink.find_by_url(args.session, args.url)
    if existing is not None:
        _report_already_saved(args.session, existing)
        return

    try:
        link = ArchivedLink.create(args.session, args.url, args.title, args.reason)
        args.session.commit()
    except IntegrityError:
        # Lost a race against a concurrent `kb ab add` for the same URL -- the unique
        # constraint on archived_link.url caught what the find_by_url check above couldn't.
        args.session.rollback()
        existing = ArchivedLink.find_by_url(args.session, args.url)
        assert existing is not None, "IntegrityError on url uniqueness but no row found by that url"
        _report_already_saved(args.session, existing)
        return
    print(link)
    print(f"AB{link.id} -- embed this ID in whatever note/todo/journal entry cites {link.url}")
    title_bytes = len(link.title.encode())
    reason_bytes = len(link.reason.encode())
    print(f"title: {link.title!r}")
    print(f"reason ({reason_bytes} bytes): {link.reason!r}")
    if title_bytes > reason_bytes:
        print(
            f"warning: title ({title_bytes} bytes) is longer than reason ({reason_bytes} bytes) "
            "-- reason is meant to carry the why, double check it isn't just a restated title"
        )

    try:
        resp = httpx.post(f"{_SERVER_BASE_URL}/ab/push", json={"link_id": link.id}, timeout=5.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"failed to queue ArchiveBox push -- is kb.service running? ({exc})", file=sys.stderr)
        sys.exit(1)

    link.push_status = ArchivedLinkPushStatus.QUEUED
    args.session.commit()

    if not args.watch:
        print(f"Queued for ArchiveBox push -- check later with `kb ab show {link.id}`")
        return

    start_dt = datetime.now()
    print(f"Watching for push result... (started {start_dt:%Y-%m-%d %H:%M:%S})")
    start = time.monotonic()
    poll_interval = 1.0
    status_interval = args.watch
    next_status_at = start + status_interval
    while True:
        args.session.expire(link)
        if link.push_status == ArchivedLinkPushStatus.SUCCESS:
            elapsed = time.monotonic() - start
            try:
                ab_url = archivebox_url(args.session, f"archive/{link.ab_id}/")
            except ArchiveBoxConfigError as exc:
                print(f"AB{link.id}: success ({elapsed:.1f}s) -- ab_url unavailable ({exc})")
                return
            print(f"AB{link.id}: success ({elapsed:.1f}s) -- {ab_url}")
            return
        if link.push_status == ArchivedLinkPushStatus.FAILED:
            elapsed = time.monotonic() - start
            print(f"AB{link.id}: failed ({elapsed:.1f}s) -- {link.push_error}", file=sys.stderr)
            sys.exit(1)
        now = time.monotonic()
        if now >= next_status_at:
            print(f"still waiting... ({now - start:.0f}s elapsed, {datetime.now():%Y-%m-%d %H:%M:%S})")
            next_status_at = now + status_interval
        time.sleep(poll_interval)


def cmd_check(args: argparse.Namespace) -> None:
    urls = args.url if args.url else [line.strip() for line in sys.stdin if line.strip()]
    if not urls:
        print("No URLs given -- pass as arguments or pipe newline-separated URLs on stdin.", file=sys.stderr)
        sys.exit(1)
    any_new = False
    for url in urls:
        existing = ArchivedLink.find_by_url(args.session, url)
        if existing is None:
            print(f"NEW: {url}")
            any_new = True
        else:
            print(f"AB{existing.id}: {url}")
    if any_new:
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    links = ArchivedLink.pending(args.session)
    if not links:
        print("No pending links.")
        return
    for link in links:
        print(f"AB{link.id} {link.created_at:%Y-%m-%d %H:%M} {link.title!r} {link.url} -- {link.reason}")


def cmd_show(args: argparse.Namespace) -> None:
    link = args.session.get(ArchivedLink, args.id)
    if link is None:
        print(f"AB{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print(link)
    print(f"url: {link.url}")
    print(f"reason: {link.reason}")
    print(f"push_status: {link.push_status.value}")
    if link.resolved_at:
        print(f"resolved_at: {link.resolved_at}")
    if link.ab_id:
        print(f"ab_id: {link.ab_id}")
        try:
            print(f"ab_url: {archivebox_url(args.session, f'archive/{link.ab_id}/')}")
        except ArchiveBoxConfigError as exc:
            print(f"ab_url: unavailable -- {exc}", file=sys.stderr)
    if link.push_error:
        print(f"push_error: {link.push_error}")
        if link.push_status == ArchivedLinkPushStatus.FAILED:
            print(f"retry with: kb ab retry {link.id}")


def cmd_fetch(args: argparse.Namespace) -> None:
    link = args.session.get(ArchivedLink, args.id)
    if link is None:
        print(f"AB{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    if not link.ab_id:
        print(f"AB{args.id}: not yet pushed to ArchiveBox, nothing to fetch", file=sys.stderr)
        sys.exit(1)
    try:
        url = archivebox_url(args.session, f"archive/{link.ab_id}/")
    except ArchiveBoxConfigError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        paragraphs = extract_paragraphs(url)
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)
    for para in paragraphs:
        print(para)


def cmd_retry(args: argparse.Namespace) -> None:
    for link_id in args.id:
        link = args.session.get(ArchivedLink, link_id)
        if link is None:
            print(f"AB{link_id}: not found", file=sys.stderr)
            continue
        resolve_or_push(args.session, link)
        if link.push_status == ArchivedLinkPushStatus.SUCCESS:
            print(f"AB{link.id}: success -- {archivebox_url(args.session, f'archive/{link.ab_id}/')}")
        else:
            print(f"AB{link.id}: failed -- {link.push_error}", file=sys.stderr)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("ab", help="ArchiveBox URL capture, pushed to the live instance best-effort")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_configure = sub.add_parser("configure", help="Set the ArchiveBox host and/or credentials (stored in OS keyring)")
    p_configure.add_argument("--host", help="ArchiveBox hostname, e.g. archivebox.internal (no scheme/path)")
    p_configure.add_argument(
        "--set-credentials", action="store_true", help="Prompt for and store the ArchiveBox staff-account login"
    )
    p_configure.set_defaults(func=cmd_configure)

    p_add = sub.add_parser(
        "add",
        help="Save a URL with a title and required reason, then queue a background push to ArchiveBox",
    )
    p_add.add_argument("url")
    p_add.add_argument("title", help="Neutral description of what the page/content is, not why it was saved")
    p_add.add_argument("reason", help="Why this was worth keeping -- what made it pass the filter")
    p_add.add_argument(
        "--watch",
        type=int,
        nargs="?",
        const=_WATCH_STATUS_INTERVAL_DEFAULT,
        default=None,
        metavar="SECONDS",
        help=(
            "Block and poll for the background push to resolve, printing success/failure and elapsed time. "
            "Optional SECONDS sets how often a still-waiting status line is printed while polling "
            f"(default {_WATCH_STATUS_INTERVAL_DEFAULT})."
        ),
    )
    p_add.set_defaults(func=cmd_add)

    p_check = sub.add_parser(
        "check",
        help="Check which URLs are already saved (AB<id>) vs NEW, without saving anything",
    )
    p_check.add_argument("url", nargs="*", help="URLs to check; if omitted, read newline-separated from stdin")
    p_check.set_defaults(func=cmd_check)

    p_list = sub.add_parser("list", help="List URLs not yet migrated to a live ArchiveBox instance")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Resolve an ABn id back to its URL/title/reason and live ArchiveBox link")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_fetch = sub.add_parser("fetch", help="Pull extracted paragraph text from the live ArchiveBox snapshot")
    p_fetch.add_argument("id", type=int)
    p_fetch.set_defaults(func=cmd_fetch)

    p_retry = sub.add_parser("retry", help="Re-attempt an ArchiveBox push for one or more failed/stuck rows")
    p_retry.add_argument("id", type=int, nargs="+")
    p_retry.set_defaults(func=cmd_retry)
