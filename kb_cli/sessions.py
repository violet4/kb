"""List Claude Code CLI sessions across all projects (~/.claude/projects/*/*.jsonl).

Distinct from kb's own data -- these are Claude Code transcript files, not kb records.
`/resume` inside Claude Code only shows sessions for the current working directory's
project folder; this surfaces every project's sessions in one place.
"""

import argparse
import json
from pathlib import Path

from kb_cli._util import print_table

_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _session_info(path: Path) -> dict[str, str] | None:
    """Return {'title', 'timestamp'} for a session transcript, or None if empty/unreadable."""
    title = None
    custom_title = None
    last_ts = None
    first_user_text = None
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = d.get("timestamp")
            if ts:
                last_ts = ts
            t = d.get("type")
            if t == "ai-title":
                title = d.get("aiTitle")
            elif t == "custom-title":
                custom_title = d.get("customTitle")
            elif t == "user" and first_user_text is None and not d.get("isMeta"):
                content = d.get("message", {}).get("content")
                if isinstance(content, str):
                    first_user_text = content
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            first_user_text = c["text"]
                            break

    resolved_title = custom_title or title or first_user_text
    if resolved_title is None or last_ts is None:
        return None
    resolved_title = " ".join(resolved_title.split())
    if len(resolved_title) > 70:
        resolved_title = resolved_title[:67] + "..."
    return {"title": resolved_title, "timestamp": last_ts}


def cmd_list(args: argparse.Namespace) -> None:
    if not _PROJECTS_DIR.is_dir():
        print(f"No sessions directory found at {_PROJECTS_DIR}")
        return

    sessions = []
    for project_dir in _PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_path in project_dir.glob("*.jsonl"):
            info = _session_info(jsonl_path)
            if info:
                sessions.append({"project": project_dir.name, **info})

    if not sessions:
        print("No sessions found.")
        return

    sessions.sort(key=lambda s: s["timestamp"], reverse=True)

    counts: dict[str, int] = {}
    for s in sessions:
        counts[s["project"]] = counts.get(s["project"], 0) + 1

    print("Directories:")
    for project, count in sorted(counts.items(), key=lambda kv: kv[0]):
        print(f"  {project}  ({count} session{'s' if count != 1 else ''})")
    print()

    headers = ["Date", "Directory", "Title"]
    rows = [[s["timestamp"][:16].replace("T", " "), s["project"], s["title"]] for s in sessions]
    print_table(headers, rows)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("sessions", help="List Claude Code CLI sessions across all projects")
    parser.set_defaults(func=cmd_list)
