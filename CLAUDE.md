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

## Goals, Todos, and Context

```bash
uv run scripts/todo show ID [ID ...]       # print Todo(s), one field per line
uv run scripts/todo complete ID [ID ...]   # mark Todo(s) done, prints each title

uv run scripts/context current       # show the active context
uv run scripts/context switch NAME   # change the active context (persists)
uv run scripts/context list          # list all known contexts, marks the active one
```

`Goal`/`Todo`/`Daily`/`Item` all take an optional `context`. Context names are a flat string convention (`"pg"`, `"pg.violet"`) — no hierarchy enforcement in the schema, just dot-separated naming. `context.py`'s `resolve_context(cli_override=None)` is the single place "what context are we acting in" is resolved: with no override it returns the persisted current context (`CurrentContext`); an override name is looked up/created via `Context.get_or_create` and does **not** change what's persisted. Any script that needs to know the active context should call `resolve_context()` rather than querying `CurrentContext`/`Context` directly.

## Before creating or updating notes

```bash
uv run scripts/notes search COLLECTION QUERY                    # semantic search, prints id/title/collection/distance
uv run scripts/notes add COLLECTION TITLE BODY [--tags t1,t2]   # add a note
uv run scripts/notes update (--id ID | --find TITLE) [--title T] [--body B] [--tags t1,t2]  # update a note
uv run scripts/notes reembed                                    # recompute embeddings for all notes
```

Check for existing related notes first with `scripts/notes search` — semantic search surfaces related notes even when you don't know the exact title. Use `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

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
uv run scripts/dev/gen-api   # regenerate api.py after every schema change
```

## Wishlist

```bash
uv run scripts/wishlist/add   # interactively add a wishlist item
```

## Model

```bash
uv run scripts/model/download   # explicitly download the embedding model (only script that hits the network)
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
