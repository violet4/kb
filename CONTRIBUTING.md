# Contributing

Bug reports and feature requests are welcome as GitHub issues — no other process needed for those.

Before starting work on a pull request, please open an issue (or comment on an existing one) describing what you'd like to change and why, and wait for a response before implementing it. This avoids duplicated effort and PRs that don't fit the project's direction — kb has fairly specific design conventions (see `AGENTS.md`) that aren't always obvious from the code alone, and it's better to align on those before writing code than after.

## Setup

See the README's Setup section for installing dependencies and running kb locally.

## Before opening a PR

```bash
scripts/dev/format .        # black
scripts/dev/check-schema    # if models.py changed
uv run pytest               # tests, with coverage
.venv/bin/mypy .            # strict type checking
```

Pre-commit hooks (installed via `scripts/dev/setup-hooks`) run black/mypy/pytest automatically on commit — the commands above are the same checks run by hand.

## Code style

See `AGENTS.md` for this project's own conventions (schema design, CLI shape, typing discipline, etc.) — it's the same guidance an AI agent working on this codebase reads before making changes, and applies equally to a human contributor.
