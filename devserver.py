#!/usr/bin/env python3
"""Dev server wrapper. Runs server.py and restarts it on any .py file change in ~/kb."""

import sys
from pathlib import Path
from watchfiles import run_process

KB_DIR = Path(__file__).parent


def main() -> None:
    run_process(
        str(KB_DIR),
        target="uv run server.py",
        target_type="command",
        watch_filter=lambda change, path: path.endswith(".py"),
    )


if __name__ == "__main__":
    main()
