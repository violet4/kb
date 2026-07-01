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

Check for existing related notes first with `client.search(query, collection)` — semantic search surfaces related notes even when you don't know the exact title. Use `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

Route anything that embeds text — search, note creation, note title/body/tag updates — through `client.py`'s `KBClient`, which talks to the always-warm `kb.service` process over a JSON socket. `KBClient` methods take the plain lowercase collection string (e.g. `"gorgon"`), not the `Collection.GORGON` enum member used in direct `sess`/model calls. Example `kb.py -f script.py` pattern:

```python
from client import KBClient
client = KBClient()
client.search("query text", "gorgon")
client.note_create(title="...", body="...", collection="gorgon", tags="...")
```

If `KBClient` can't connect (`kb.service` down — check `systemctl --user status kb.service`), fall back to the direct model methods (`Note.create`, `.search`, `.reembed`), which load their own copy of the embedding model.

## Server

The embedding server runs as a systemd user service (`kb.service`) and stays warm for `client.py` to use.

## Schema changes

```bash
uv run alembic revision --autogenerate -m "describe"
uv run alembic upgrade head
uv run scripts/gen-api.py   # regenerate api.py after every schema change
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
