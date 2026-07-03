# KB — Claude instructions

Personal knowledge base. SQLite + SQLAlchemy 2.0. Run `scripts/dev/gen-api` for the full model/method surface before making any queries or updates. Every script here (including `kb.py`) is directly executable from any directory — no `uv run` prefix needed, the shebang handles it.

kb is not a fixed system to work around — it's meant to be continuously refined. When a real access pattern doesn't fit cleanly (a script that's clunky to drive, a field that's always empty or always guessed, a query that has to be re-derived each time), that's a signal to change the schema/script/doc, not a one-off workaround to route past it. Treat friction encountered while using kb as input to kb's own design, the same way Goal #14 (kbui) treats interaction friction as input to that design.

`scripts/dev/gen-api [ClassName ...]` prints the collapsed view — every entity, field, method, and signature, no implementation — always current since it's generated live from `models.py`, not a file to regenerate and re-read. `models.py` is the expanded view, read only when implementation details are actually needed. Load the collapsed view by default; expand only the specific piece you need.

Cache stable-but-frequently-referenced facts locally (e.g. game mechanics, reference lore) rather than re-looking them up every time — that's the point of kb. Don't cache genuinely volatile info (stock prices, weather, anything that changes on its own) as if it were a stable fact; look that up fresh when it's needed instead.

## Dashboard

```bash
summary [goals|todos|people|wishlist ...]   # active/pending overview; no args shows all sections
```

## Running commands

`scripts/<domain> <verb> [args]` — every domain script is one file with argparse subcommands; `<domain> --help` lists them all. This section covers the runner itself (`kb.py`); later sections list each domain's verbs without repeating this shape.

```bash
kb.py "sess.scalars(select(Note)).all()"   # single command, auto-commits
kb.py -f script.py                          # run a script file, auto-commits (use for multi-line bodies)
kb.py --no-commit "..."                     # dry-run
kb.py -i                                    # interactive REPL, explicit opt-in — does NOT auto-commit
```

Bare `kb.py` (no command, `-f`, or `-i`) errors instead of silently dropping into the REPL — always pass `-i` explicitly if you want manual-commit interactive mode.

`sess` and all models are pre-loaded, including game-specific ones (`PgPlayer`, `PgNpc`, `PgQuest`, `PgItem`, ...). No imports needed. Everything shares a single database and session.

`--context NAME` acts in that context for one command only (pre-loaded as `context` in the namespace) without changing the persisted current context — e.g. `./kb.py --context pg.violet "Goal.active(context)"`.

Enum columns take the member (uppercase name, e.g. `Collection.GORGON`), not the lowercase `.value` shown in old muscle memory. `scripts/dev/gen-api` lists valid members per enum.

## Goals, Todos, and Context

```bash
goal show|complete|abandon|hold|reactivate ID [ID ...]   # hold = blocked externally, not abandoned
todo show ID [ID ...] | add TITLE [--effort grab|research|project] [--notes N] | complete ID [ID ...] | pending [--effort grab|research|project]
context current | switch NAME | list
```

`Todo.effort` (reusing `WishlistEffort`) marks how much a Todo actually takes — `grab` for something quick/batchable now, `research`/`project` for bigger asks — so `todo pending --effort grab` finds exactly the small stuff worth batching, without it getting lost among everything else.

`Goal`/`Todo`/`Daily`/`Item` all take an optional `context`. Context names are a flat string convention (`"pg"`, `"pg.violet"`) — no hierarchy enforcement in the schema, just dot-separated naming. `context.py`'s `resolve_context(cli_override=None)` is the single place "what context are we acting in" is resolved: with no override it returns the persisted current context (`CurrentContext`); an override name is looked up/created via `Context.get_or_create` and does **not** change what's persisted. Any script that needs to know the active context should call `resolve_context()` rather than querying `CurrentContext`/`Context` directly.

## Before creating or updating notes

```bash
notes get ID | search COLLECTION QUERY | add COLLECTION TITLE BODY [--tags t1,t2] | update (--id ID|--find TITLE) [--title T] [--body B] [--tags t1,t2] | reembed
```

Check for existing related notes first with `notes search` — semantic search surfaces related notes even when you don't know the exact title. Use `notes get ID` once you have an id (e.g. from a `kb-<collection>-<id>` pointer), and `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

## Server

The embedding server runs as a systemd user service (`kb.service`). `embed()` (in `embed.py`, used internally by `Note.create`/`.search`/`.reembed`) automatically routes through the warm server when it's running, falling back to loading a local model only if the server is down — this is transparent, no need to route through `client.py` manually.

```bash
service/status | restart | is-active
```

## Schema changes

Add a column when something needs to be filtered or sorted on; use a `notes: Text` field for anything you just want to remember. Start with more in `notes` and promote to a real column once a real query need shows up.

```bash
alembic revision --autogenerate -m "describe"   # review before applying — autogenerate misses column
                                                  # renames (sees drop+add, write those by hand), data
                                                  # migrations (add a manual step), and Enum CHECK
                                                  # constraint changes on SQLite (see kb-engineering-10)
alembic upgrade head
alembic current | history | downgrade -1
```

Enum columns are constrained at the DB level (`Enum(..., create_constraint=True, validate_strings=True)`) — see kb-engineering-10 before adding a new `Enum(...)` column. Adding a new *value* to an existing enum still needs a migration to update the CHECK constraint; use a raw-SQL table recreate (CREATE + INSERT SELECT + DROP + RENAME), not `batch_alter_table`/`alter_column` — see kb-engineering-16 and `alembic/versions/752237ed2641_add_on_hold_to_goalstatus.py` for why and a worked example.

## Wishlist, Model

```bash
wishlist/add TITLE [--description D] [--price-min N] [--price-max N] [--importance N] [--urgency N] [--clarity N] [--effort grab|research|project] [--priority N] [--notes N]
model/download      # explicitly download the embedding model (only script that hits the network)
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
