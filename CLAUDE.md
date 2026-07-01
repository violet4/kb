# KB — Claude instructions

Personal knowledge base. SQLite + SQLAlchemy 2.0. Read `api.py` for the full model/method surface before making any queries or updates.

## Running commands

```bash
uv run kb.py "sess.scalars(select(Note)).all()"   # single command, auto-commits
uv run kb.py -f script.py                          # run a script file, auto-commits (use for multi-line bodies)
uv run kb.py --no-commit "..."                     # dry-run
uv run kb.py -i                                    # interactive REPL, explicit opt-in — does NOT auto-commit
```

Bare `kb.py` (no command, `-f`, or `-i`) errors instead of silently dropping into the REPL — always pass `-i` explicitly if you want manual-commit interactive mode.

`sess` and all models are pre-loaded. No imports needed.

Enum columns take the member (uppercase name, e.g. `Collection.GORGON`), not the lowercase `.value` shown in old muscle memory — e.g. `Note.search(query, Collection.GORGON)`. `api.py` lists valid members per enum.

## Before creating or updating notes

Check for existing related notes first with `Note.search(query, collection)` — semantic search surfaces related notes even when you don't know the exact title. Use `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

## Server

The embedding server runs as a systemd user service (`kb.service`). `embed()` (in `embed.py`, used internally by `Note.create`/`.search`/`.reembed`) automatically routes through the warm server when it's running, falling back to loading a local model only if the server is down — this is transparent, no need to route through `client.py` manually from `kb.py` scripts.

```bash
scripts/service/status      # check whether kb.service is up
scripts/service/restart     # restart kb.service (e.g. after changing embed.py/server.py/models.py)
scripts/service/is-active   # quick active/inactive check
```

## Schema changes

```bash
uv run alembic revision --autogenerate -m "describe"
uv run alembic upgrade head
uv run scripts/gen-api.py   # regenerate api.py after every schema change
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
