"""Notification delivery + settings. Owns what a notification *is* (desktop
notify-send, ntfy push, sound) and whether it should fire at all right now
(mute, volume) -- persisted once in Settings so every harness adapter picks up
the same state without re-implementing it. A harness adapter (e.g.
harnesses/claude-code/notify-claude) stays a thin extraction of that harness's
own event data into plain text/flags, piped into `kb notifications send`."""

import argparse
import subprocess
from pathlib import Path

from models import Settings

_DEFAULT_NTFY_URL = "http://localhost:7182/claude-code"
_DEFAULT_NTFY_TOKEN_FILE = Path.home() / ".config" / "ntfy-token"


def cmd_mute(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    settings.notifications_muted = True
    args.session.commit()
    print("Notifications muted.")


def cmd_unmute(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    settings.notifications_muted = False
    args.session.commit()
    print("Notifications unmuted.")


def cmd_volume(args: argparse.Namespace) -> None:
    if not 0 <= args.level <= 100:
        raise SystemExit("volume: must be between 0 and 100")
    settings = Settings.get(args.session)
    settings.notifications_volume = args.level
    args.session.commit()
    print(f"Notification volume set to {args.level}.")


def cmd_status(args: argparse.Namespace) -> None:
    settings = Settings.get(args.session)
    state = "muted" if settings.notifications_muted else "unmuted"
    print(f"Notifications: {state}, volume {settings.notifications_volume}")


def _ntfy_url(args: argparse.Namespace) -> str:
    base = args.ntfy_url or _DEFAULT_NTFY_URL
    if args.ntfy_topic:
        base = base.rsplit("/", 1)[0] + "/" + args.ntfy_topic
    return base


def cmd_send(args: argparse.Namespace) -> None:
    """Deliver one notification: desktop notify-send + sound (via ~/bin/beep) unless
    muted or --ntfy-only, and an ntfy push if a token file is configured -- ntfy pushes
    still fire while muted, since mute means "don't bother me locally", not "don't tell
    my phone"."""
    settings = Settings.get(args.session)

    title = args.title
    body = args.body or "No further detail."

    if not settings.notifications_muted and not args.ntfy_only:
        _run_best_effort(["notify-send", title, body])
        _run_best_effort(["beep", "--volume", str(settings.notifications_volume), "--async"])

    ntfy_token_file = Path(args.ntfy_token_file or _DEFAULT_NTFY_TOKEN_FILE)
    if ntfy_token_file.is_file():
        ntfy_token = ntfy_token_file.read_text().strip()
        priority = "high" if args.priority == "high" else "default"
        _run_best_effort(
            [
                "curl",
                "-fsS",
                "-m",
                "5",
                "-H",
                f"Authorization: Bearer {ntfy_token}",
                "-H",
                f"Title: {title}",
                "-H",
                f"Priority: {priority}",
                "-d",
                body,
                _ntfy_url(args),
            ]
        )


def _run_best_effort(cmd: list[str]) -> None:
    """Delivery channels here are non-critical side effects (a desktop popup, a
    sound, a push) -- a missing binary or network hiccup shouldn't fail the
    invoking hook, only the delivery attempt itself."""
    try:
        subprocess.run(cmd, check=False, capture_output=True)
    except OSError:
        pass


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "notifications", aliases=["notify"], help="Notification delivery + mute/volume settings"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mute = sub.add_parser("mute", help="Suppress desktop notification + sound (ntfy still fires)")
    p_mute.set_defaults(func=cmd_mute)

    p_unmute = sub.add_parser("unmute", help="Re-enable desktop notification + sound")
    p_unmute.set_defaults(func=cmd_unmute)

    p_volume = sub.add_parser("volume", help="Set notification sound volume (0-100)")
    p_volume.add_argument("level", type=int, metavar="0-100")
    p_volume.set_defaults(func=cmd_volume)

    p_status = sub.add_parser("status", help="Show current mute/volume settings")
    p_status.set_defaults(func=cmd_status)

    p_send = sub.add_parser("send", help="Deliver one notification (desktop + sound + ntfy), honoring current settings")
    p_send.add_argument("title", help="Notification title")
    p_send.add_argument("body", nargs="?", default=None, help="Notification body (default: 'No further detail.')")
    p_send.add_argument("--priority", choices=["default", "high"], default="default", help="ntfy push priority")
    p_send.add_argument("--ntfy-url", help=f"Override ntfy URL (default: {_DEFAULT_NTFY_URL} or $NTFY_URL)")
    p_send.add_argument(
        "--ntfy-topic",
        metavar="NAME",
        help="Send to a different ntfy topic, keeping the same base URL (replaces the last path segment)",
    )
    p_send.add_argument(
        "--ntfy-token-file",
        help=f"Override ntfy token file path (default: {_DEFAULT_NTFY_TOKEN_FILE} or $NTFY_TOKEN_FILE)",
    )
    p_send.add_argument(
        "--ntfy-only",
        action="store_true",
        help="Skip desktop notify-send + sound; only push via ntfy (for headless use)",
    )
    p_send.set_defaults(func=cmd_send)
