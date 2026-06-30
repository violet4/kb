# KB — Claude instructions

Personal knowledge base. SQLite + SQLAlchemy 2.0. Read `api.py` for the full model/method surface before making any queries or updates.

## Running commands

```bash
uv run kb.py "sess.scalars(select(Note)).all()"   # single command, auto-commits
uv run kb.py --no-commit "..."                     # dry-run
uv run kb.py                                       # interactive REPL
```

`sess` and all models are pre-loaded. No imports needed.

## Server

The embedding server runs as a systemd user service (`kb.service`). For Note search and creation, prefer `client.py` when the server is running — it keeps the model warm. Fall back to direct model calls if the server is down.

## Schema changes

```bash
uv run alembic revision --autogenerate -m "describe"
uv run alembic upgrade head
uv run scripts/gen-api.py   # regenerate api.py after every schema change
```
