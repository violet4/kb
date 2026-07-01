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

Check for existing related notes first with `Note.find(title)` or `Note.search(query, collection)` — never dump full note bodies or list a whole collection to survey it.

## Server

The embedding server runs as a systemd user service (`kb.service`). For Note search and creation, prefer `client.py` when the server is running — it keeps the model warm. Fall back to direct model calls if the server is down.

## Schema changes

```bash
uv run alembic revision --autogenerate -m "describe"
uv run alembic upgrade head
uv run scripts/gen-api.py   # regenerate api.py after every schema change
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
