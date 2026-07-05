# KB — Claude instructions

Personal knowledge base. SQLite + SQLAlchemy 2.0. Run `scripts/dev/gen-api` for the full model/method surface before making any queries or updates. Every script here (including `kb.py`) is directly executable from any directory — no `uv run` prefix needed, the shebang handles it.

`kb <command> [subcommand ...] [args]` is the global CLI entry point (`~/bin/kb` symlinks to `~/kb/kb`), usable from any directory on the filesystem, not just from inside `~/kb`. It dispatches to `kb_cli/*.py` — real importable Python modules (not standalone executables), each exposing an `add_subparser(subparsers)` hook that the top-level `kb` script wires into one argparse tree. `kb <command> --help` (at any nesting depth, e.g. `kb games pg entity mob --help`) documents itself natively. This covers Goal/Todo/Inbox/Journal/Notes/Log/Context/Summary/Wishlist and per-game commands (`kb games pg ...`) — anything meant to be reachable no matter which project you're currently working in. `scripts/db`, `scripts/dev`, `scripts/model`, `scripts/service` stay as plain `scripts/*` executables, kb-repo-local only, since migrating/checking schema/etc. only makes sense while actually developing kb itself — mirrors the split between `~/kb/CLAUDE.md` (this file, kb-repo-local) and `~/kb/CLAUDE_GLOBAL.md` (symlinked from `~/.claude/CLAUDE.md`, global).

If asked "what were we working on" (or similar) at the start of a session, answer from the database before git history: `kb summary` for active Goals/Todos/wishlist/inbox, `kb goal show ID --history`/`kb journal show ENTITY_TYPE ID` for a specific Goal or Todo's full design history, `kb inbox pending` for unfiled ideas. `git log` shows what code changed; it doesn't show what's still open or why — kb's own tables are the actual answer to "what were we working on."

kb is not a fixed system to work around — it's meant to be continuously refined. When a real access pattern doesn't fit cleanly (a script that's clunky to drive, a field that's always empty or always guessed, a query that has to be re-derived each time), that's a signal to change the schema/script/doc, not a one-off workaround to route past it. Treat friction encountered while using kb as input to kb's own design, the same way Goal #14 (kbui) treats interaction friction as input to that design.

`scripts/dev/gen-api [ClassName ...]` prints the collapsed view — every entity, field, method, and signature, no implementation — always current since it's generated live from `models.py`, not a file to regenerate and re-read. `models.py` is the expanded view, read only when implementation details are actually needed. Load the collapsed view by default; expand only the specific piece you need.

`models_pg.py` holds every Project Gorgon-specific table (`PgPlayer`, `PgNpc`, `PgQuest`, `PgItem`, ...) — split out from `models.py` since it's a large, rarely-needed chunk when working on kb's shared core. Read `models.py` for anything domain-agnostic; only read `models_pg.py` when actually working on pg-specific tables. Any file that imports `Base`/`Item` and registers new tables at import time (alembic's `env.py`, `scripts/dev/check-schema`) must import `models_pg` too, or its tables won't be seen by migrations/schema checks.

Cache stable-but-frequently-referenced facts locally (e.g. game mechanics, reference lore) rather than re-looking them up every time — that's the point of kb. Don't cache genuinely volatile info (stock prices, weather, anything that changes on its own) as if it were a stable fact; look that up fresh when it's needed instead.

## Dashboard

```bash
kb summary [goals|todos|people|wishlist|inbox ...]   # active/pending overview; no args shows all sections
```

## Inbox

```bash
kb inbox add BODY [--source S] [--category C]   # raw, untriaged capture
kb inbox pending [--category C]                 # list untriaged items, optionally filtered
kb inbox triage ID [ID ...]                     # mark triaged, after creating whatever real record it became
```

`InboxItem` is for anything whose eventual home isn't known yet — unlike every other kb table, you don't decide up front whether it's a `Todo`, a `Purchase`, a `LogEntry`, or nothing at all. Triage means: create the real record it turns out to be, then `inbox triage` the item. Don't let ideas-in-passing get lost while mid-task — `inbox add` them and keep moving.

`source` (capture channel: `email`, `mobile`, `quick-note`) and `category` (kind of content: `project-idea`, `purchase`) are separate axes — filter `pending` by `category` to triage a large backlog in batches by kind before deciding each item's final home.

## Running commands

`kb <command> <verb> [args]` — every command group is a `kb_cli/*.py` module with argparse subcommands, wired into one global entry point; `kb <command> --help` lists them all. This section covers the Python-expression runner (`kb.py`), a different tool from the `kb` CLI — `kb.py` is for one-off queries/scripts against models directly, `kb` is for the day-to-day subcommands documented in the sections below.

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
kb goal show|complete|abandon|hold|reactivate ID [ID ...]   # hold = blocked externally, not abandoned
kb goal add TITLE [--description D] [--notes N] [--context NAME]
kb todo show ID [ID ...] | add TITLE [--effort grab|research|project] [--defer-until WHEN] [--notes N] [--context NAME] | update ID [--title T] [--effort E] [--defer-until WHEN] [--notes N] [--context NAME] [--goal ID] | complete ID [ID ...] | pending [--effort grab|research|project] [--all]
kb context current | switch NAME | list
```

`goal show`/`todo show` print a one-line "N history entries" hint when Journal history exists, without dumping it — pass `--history` to expand it inline, or `--history N` for just the last N entries.

`Todo.defer_until` hides a Todo from `todo pending`/`kb summary` until that time passes — not a due date, a "don't show me this until it's actually relevant" filter (e.g. "vacuum" deferred to 19:00 today doesn't clutter the view until evening planning time). `--defer-until` accepts `HH:MM` (today, or tomorrow if that time already passed), `YYYY-MM-DD`, or `YYYY-MM-DD HH:MM`. `todo pending --all` (or `Todo.pending(include_deferred=True)`) surfaces deferred-but-not-yet-due items too, for deliberately planning ahead.

SQLite silently drops timezone info on `DateTime(timezone=True)` columns on read-back (the column stores it, but the Python value comes back naive) — any code comparing a stored datetime against a fresh `datetime.now(timezone.utc)` in Python must `.replace(tzinfo=timezone.utc)` first, or the comparison raises `TypeError`. SQL-level comparisons (inside a `select(...).where(...)`) aren't affected, only Python-level comparisons after the ORM has already loaded the value.

## Log and Journal

```bash
kb log add BODY [--domain D] [--context NAME] [--date YYYY-MM-DD]   # timestamped observation; --date backdates (default: now)
kb log recent [--domain D] [--context NAME] [--limit N]
kb journal add ENTITY_TYPE ENTITY_ID NOTE   # record a free-text journal note for an entity
kb journal show ENTITY_TYPE ENTITY_ID
```

`LogEntry` is a fact about the world at a point in time (health, events, work log) — not durable reference knowledge (`Note`) and not work with a status (`Goal`/`Todo`). See `LogEntry`'s docstring in `models.py` for the full distinction, and the `Journal` note in the Price/purchase history section below for how `Journal` (structured per-entity history) differs from both.

`Todo.effort` (reusing `WishlistEffort`) marks how much a Todo actually takes — `grab` for something quick/batchable now, `research`/`project` for bigger asks — so `todo pending --effort grab` finds exactly the small stuff worth batching, without it getting lost among everything else.

`Goal`/`Todo`/`Daily`/`Item` all take an optional `context`. Context names are a flat string convention (`"pg"`, `"pg.violet"`) — no hierarchy enforcement in the schema, just dot-separated naming. `context.py`'s `resolve_context(cli_override=None)` is the single place "what context are we acting in" is resolved: with no override it returns the persisted current context (`CurrentContext`); an override name is looked up/created via `Context.get_or_create` and does **not** change what's persisted. Any script that needs to know the active context should call `resolve_context()` rather than querying `CurrentContext`/`Context` directly.

## Before creating or updating notes

```bash
kb notes get ID | search COLLECTION QUERY | add COLLECTION TITLE BODY [--tags t1,t2] | update (--id ID|--find TITLE) [--title T] [--body B] [--tags t1,t2] | reembed
```

Check for existing related notes first with `notes search` — semantic search surfaces related notes even when you don't know the exact title. Use `notes get ID` once you have an id (e.g. from a `kb-<collection>-<id>` pointer), and `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

## Server

The embedding server runs as a systemd user service (`kb.service`). `embed()` (in `embed.py`, used internally by `Note.create`/`.search`/`.reembed`) automatically routes through the warm server when it's running, falling back to loading a local model only if the server is down — this is transparent, no need to route through `client.py` manually.

```bash
scripts/service/status | restart | is-active
```

## Schema changes

Add a column when something needs to be filtered or sorted on; use a `notes: Text` field for anything you just want to remember. Start with more in `notes` and promote to a real column once a real query need shows up.

```bash
scripts/dev/check-schema             # verify models.py builds cleanly (in-memory) before generating a migration
scripts/db/migrate "describe"        # check-schema, then alembic revision --autogenerate — review the file before applying
scripts/db/upgrade                   # alembic upgrade head
scripts/db/status                    # alembic current
```

Autogenerate misses column renames (sees drop+add, write those by hand), table renames' own constraints (see below), data migrations (add a manual step), and Enum CHECK constraint changes on SQLite (see kb-engineering-10).

Enum columns are constrained at the DB level (`Enum(..., create_constraint=True, validate_strings=True)`) — see kb-engineering-10 before adding a new `Enum(...)` column. Adding a new *value* to an existing enum still needs a migration to update the CHECK constraint; use a raw-SQL table recreate (CREATE + INSERT SELECT + DROP + RENAME), not `batch_alter_table`/`alter_column` — see kb-engineering-16 and `alembic/versions/752237ed2641_add_on_hold_to_goalstatus.py` for why and a worked example.

Read kb-engineering-20 before renaming any table's `__tablename__` (e.g. a `PgFoo`->`PgBar` rename): `op.rename_table` renames only the table, never its own PK/UNIQUE/CHECK constraints, so the same raw-SQL table recreate as kb-engineering-16 is needed in the same migration to bring those constraint names in line with what the naming convention now expects. Autogenerate does not flag this drift until a much later, unrelated migration surfaces it as a confusing diff — fix it immediately in the rename's own migration, not later.

Read the newest engineering note on `batch_alter_table` column renames before renaming any column that has a foreign key: a `drop_constraint`/`create_foreign_key` pair issued inside the *same* `batch_alter_table` block as the column rename can silently fail to apply, leaving the FK missing entirely with no error. Put the FK recreation in a separate migration (or separate `batch_alter_table` block) from the rename itself, and always run the throwaway `scripts/db/migrate "verify no-op"` check afterward — that's what actually caught this the one time it happened.

## Price/purchase history

`Vendor`/`VendorItem`/`Purchase` track price and quantity over time for anything transactable, real or in-game — a grocery store and a PG player-shop NPC are both a `Vendor` (`domain="irl"`/`"pg"`), since neither shows a full price history at once, only snippets over time. `Item.upc` is the universal barcode (same everywhere); `VendorItem.vendor_sku` is that vendor's own code for the item (may differ store to store). Look up a scanned/typed code against `Item.upc` first, then `VendorItem.vendor_sku` for that vendor, before prompting to create a new `Item`. Real-world items are `IrlItem(Item, HasWeight)`, matching `PgItem`'s JTI pattern — every `Item` subtype needs its own `polymorphic_identity`, a bare `Item(game="whatever")` with no matching subclass breaks reads.

`Journal` is structured change history for any entity (`entity_type`, `entity_id`, optional `field`/`old_value`/`new_value`/`note`) — distinct from `LogEntry` (a fact about the world, not tied to a record) and `Note` (durable reference knowledge, not history). `journal show ENTITY_TYPE ENTITY_ID` (e.g. `journal show Goal 14`) reads it. Keep a `Goal`/`Todo`'s `description`/`notes` as lean, current understanding — move decision-by-decision history into `Journal` entries instead of letting it accumulate in the record itself.

## Wishlist, Model

```bash
kb wishlist add TITLE [--description D] [--price-min N] [--price-max N] [--importance N] [--urgency N] [--clarity N] [--effort grab|research|project] [--priority N] [--notes N]
kb wishlist update ID [--title T] [--description D] [--price-min N] [--price-max N] [--importance N] [--urgency N] [--clarity N] [--effort E] [--priority N] [--status active|acquired|dropped] [--notes N]
scripts/model/download      # explicitly download the embedding model (only script that hits the network)
```

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
