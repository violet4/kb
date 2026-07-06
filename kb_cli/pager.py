"""Page through a large file in small chunks across repeated invocations.

State is external (no interactivity possible), keyed by a hash of the file's
absolute path, stored under /tmp -- not meant to survive a reboot, and only
one pager instance per file is supported at a time.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

STATE_DIR = Path("/tmp/kb-pager")
MAX_LINE_LEN = 500
DEFAULT_LINES = 20


def _state_path(abspath: str) -> Path:
    digest = hashlib.sha256(abspath.encode()).hexdigest()[:16]
    return STATE_DIR / f"{digest}.json"


def _load_state(state_path: Path, mtime: float) -> int:
    if not state_path.exists():
        return 0
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(state, dict) or state.get("mtime") != mtime:
        return 0
    line_offset = state.get("line_offset", 0)
    return line_offset if isinstance(line_offset, int) else 0


def _save_state(state_path: Path, abspath: str, mtime: float, line_offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"path": abspath, "mtime": mtime, "line_offset": line_offset}))


def _truncate(line: str) -> str:
    if len(line) > MAX_LINE_LEN:
        return line[:MAX_LINE_LEN] + "..."
    return line


def cmd_page(args: argparse.Namespace) -> None:
    path = Path(args.file).resolve()
    if not path.is_file():
        print(f"pager: {args.file}: not found", file=sys.stderr)
        sys.exit(1)

    abspath = str(path)
    mtime = path.stat().st_mtime
    state_path = _state_path(abspath)

    offset = 0 if args.reset else _load_state(state_path, mtime)

    lines = path.read_text(errors="replace").splitlines()
    total = len(lines)

    if offset >= total:
        print("-- EOF --")
        state_path.unlink(missing_ok=True)
        return

    chunk = lines[offset:offset + args.lines]
    for line in chunk:
        print(_truncate(line))

    new_offset = offset + len(chunk)
    if new_offset >= total:
        print("-- EOF --")
        state_path.unlink(missing_ok=True)
    else:
        _save_state(state_path, abspath, mtime, new_offset)
        print(f"-- lines {offset + 1}-{new_offset} of {total}, run again to continue --", file=sys.stderr)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("pager", help="Page through a large file in chunks, one invocation per chunk")
    parser.add_argument("file")
    parser.add_argument("--lines", type=int, default=DEFAULT_LINES, help=f"Lines per chunk (default {DEFAULT_LINES})")
    parser.add_argument("--reset", action="store_true", help="Start over from the beginning")
    parser.set_defaults(func=cmd_page)
