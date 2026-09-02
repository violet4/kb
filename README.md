# kb — Personal Knowledge Base

A persistent, queryable store for notes, goals, todos, and reference knowledge — SQLite + SQLAlchemy, with vector search over notes/goals/todos so they're discoverable by meaning, not just exact wording. Usage is interactive and self-discovering: run bare `kb` for a task-oriented routing guide, `kb -h` for the full technical reference, or `kb <noun> --help` for one command's flags — the live entity/method surface is `scripts/dev/gen-api`, not a table in this file, so it never goes stale.

This README covers only what setup requires or what isn't easily discovered by running `kb` itself. See `CLAUDE.md` for architecture and the reasoning behind kb's conventions, and `docs/` for anything too long to keep in either.

## Setup (first clone, or a new machine)

Requires [uv](https://docs.astral.sh/uv/) — every script here (including `kb`/`kb_repl.py`) is directly executable via a `uv run` shebang, so `uv` itself must already be on `PATH` before anything below will run.

```bash
uv sync                        # install dependencies
scripts/model/download         # fetch the embedding model from HuggingFace once; after this, embedding runs offline/local
scripts/db/upgrade             # apply migrations
scripts/dev/setup-hooks        # install git pre-commit/post-commit hooks (idempotent, safe to re-run)
scripts/service/restart        # start the embedding server (kb.service, systemd user unit)
```

`~/bin/kb` should symlink to this repo's `kb` script so `kb <command>` works from any directory. Every script here (including `kb`/`kb_repl.py`) is directly executable — the shebang handles `uv run`, no prefix needed.

## Connecting a harness (Claude Code, or another agent tool)

The LLM itself holds no memory between conversations — every model instance is generic and stateless, shared across every user of that model. kb is what supplies continuity: identity, history, and personal context live here, not in the model, which is why kb must work the same regardless of which harness or which LLM is driving it.

kb's own content (the Instruction tree, `kb hooks` detectors, Goals/Todos/Notes) works from any harness driving it — a harness supplies only the trigger mechanism, never a second copy of kb's own logic (see `CLAUDE.md`'s harness paragraph). See `docs/harnesses/` for per-harness wiring instructions, one file per harness, covering every hook set up for it.

## Server

```bash
scripts/service/status
scripts/service/restart
scripts/service/is-active
```
