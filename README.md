# kb — Personal Knowledge Base

A persistent, queryable store for notes, goals, todos, and reference knowledge — SQLite + SQLAlchemy, with vector search over notes/goals/todos so they're discoverable by meaning, not just exact wording. Usage is interactive and self-discovering: run bare `kb` for a task-oriented routing guide, `kb -h` for the full technical reference, or `kb <noun> --help` for one command's flags — the live entity/method surface is `scripts/dev/gen-api`, not a table in this file, so it never goes stale.

This README covers only what setup requires or what isn't easily discovered by running `kb` itself. See `CLAUDE.md` for architecture and the reasoning behind kb's conventions, and `docs/` for anything too long to keep in either.

## Setup (first clone, or a new machine)

Requires [uv](https://docs.astral.sh/uv/) — every script here (including `kb`/`kb_repl.py`) is directly executable via a `uv run` shebang, so `uv` itself must already be on `PATH` before anything below will run. Clone this repo to `~/kb` — `kb.service` (below) assumes that path.

```bash
uv sync                        # install dependencies
scripts/model/download         # fetch the embedding model from HuggingFace once; after this, embedding runs offline/local
scripts/db/upgrade             # apply migrations, creating data/kb.db on first run
scripts/dev/setup-hooks        # install git pre-commit/post-commit hooks (idempotent, safe to re-run)
```

Symlink `kb` onto `PATH` so `kb <command>` works from any directory, not just from inside this repo:

```bash
mkdir -p ~/bin
ln -sfn ~/kb/kb ~/bin/kb       # re-run after moving/renaming the clone; safe to re-run any time
```

Make sure `~/bin` is itself on `PATH` (add `export PATH="$HOME/bin:$PATH"` to your shell profile if it isn't already).

### Embedding server (kb.service)

Semantic search (`kb search`, `kb notes search`, ...) needs the embedding server running. It's a systemd user unit, installed once by symlinking the tracked service file into systemd's user unit directory:

```bash
mkdir -p ~/.config/systemd/user
ln -sfn ~/kb/kb.service ~/.config/systemd/user/kb.service
systemctl --user daemon-reload
systemctl --user enable --now kb.service
```

After that one-time install, use the wrapper scripts day to day:

```bash
scripts/service/status
scripts/service/restart
scripts/service/is-active
```

kb still works without this running — `embed()` falls back to loading the embedding model directly in-process when the server is down, just slower per call (see `CLAUDE.md`'s Server section).

### Frontend (optional web UI)

The web UI is optional — everything in kb is usable from the CLI alone. To run it:

```bash
cd frontend
npm install
npm run dev                    # Vite dev server on :25691, proxies /api to the backend on :25690
```

The backend it proxies to is `server.py`, served by `kb.service` above (`devserver.py` runs `server.py` and restarts it on `.py` file changes) — start that first, or `kb search`-style API calls from the frontend will fail. `npm run dev` is a manual foreground process; to run the frontend as a background service the same way as the backend, install `frontend/kb-frontend-dev.service` the same way as `kb.service` above (symlink into `~/.config/systemd/user/`, `daemon-reload`, `enable --now`).

## Connecting a harness (Claude Code, or another agent tool)

The LLM itself holds no memory between conversations — every model instance is generic and stateless, shared across every user of that model. kb is what supplies continuity: identity, history, and personal context live here, not in the model, which is why kb must work the same regardless of which harness or which LLM is driving it.

kb's own content (the Instruction tree, `kb hooks` detectors, Goals/Todos/Notes) works from any harness driving it — a harness supplies only the trigger mechanism, never a second copy of kb's own logic (see `CLAUDE.md`'s harness paragraph). See `docs/harnesses/` for per-harness wiring instructions, one file per harness, covering every hook set up for it.
