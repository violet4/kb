# KB — Claude instructions

Personal knowledge base. SQLite + SQLAlchemy 2.0. Run `scripts/dev/gen-api` for the full model/method surface before making any queries or updates. Every script here (including `kb.py`) is directly executable from any directory — no `uv run` prefix needed, the shebang handles it.

`kb <command> [subcommand ...] [args]` is the global CLI entry point (`~/bin/kb` symlinks to `~/kb/kb`), usable from any directory on the filesystem, not just from inside `~/kb`. It dispatches to `kb_cli/*.py` — real importable Python modules (not standalone executables), each exposing an `add_subparser(subparsers)` hook that the top-level `kb` script wires into one argparse tree. Routing (which noun for which kind of statement) lives in bare `kb`'s own output, not here; syntax/flags for a given command live in that command's own `--help` at any nesting depth (e.g. `kb games pg entity mob --help`), always current since it's generated from the actual argparse definitions — don't duplicate either into this file. `scripts/db`, `scripts/dev`, `scripts/model`, `scripts/service` stay as plain `scripts/*` executables, kb-repo-local only, since migrating/checking schema/etc. only makes sense while actually developing kb itself — mirrors the split between `~/kb/CLAUDE.md` (this file, kb-repo-local, project architecture/why) and `kb i root` / bare `kb` (global, routing/day-to-day usage).

`kb --context NAME <command> ...` is a global flag on the top-level `kb` script itself (parsed before dispatch, in `kb`, not in any `kb_cli/*.py` subparser) — it resolves once via `resolve_context()` into `args.context`, already a `Context` object, and every subcommand that accepts a context (e.g. `goal add`, `todo add`) just forwards `args.context` straight through without declaring its own `--context` argument. Don't add a per-subcommand `--context` flag to a `kb_cli/*.py` module expecting it to work like this global one; only `todo update` has its own `--context NAME` (a string, resolved inside that command) for changing an existing record's context after the fact, which is a different, per-command flag from this global one.

If asked "what were we working on" (or similar) at the start of a session, answer from the database before git history: kb's own tables (Goal/Todo/Journal/Inbox — see `kb -h`/`kb summary --help`) are the actual answer, not `git log`, which shows what code changed but not what's still open or why.

"kb" alone is ambiguous between the CLI/repo and the `Context` tree's own top-level "kb" node (`irl/projects/kb`, visible in `kb context tree`). When a request says "add X under kb" or "a new context/command alongside Y" and Y resolves to something in `kb context tree` output (a `Context` row, e.g. `timer` at `irl/projects/kb/timer`) rather than a `kb_cli/*.py` module, read it as a `Context` tree placement (`kb context add X --parent ...`), not a new CLI command module — check `kb context tree` for the named sibling before assuming which one is meant.

kb is not a fixed system to work around — it's meant to be continuously refined. When a real access pattern doesn't fit cleanly (a script that's clunky to drive, a field that's always empty or always guessed, a query that has to be re-derived each time), that's a signal to change the schema/script/doc, not a one-off workaround to route past it. Treat friction encountered while using kb as input to kb's own design, the same way Goal #14 (kbui) treats interaction friction as input to that design.

`scripts/dev/gen-api [ClassName ...]` prints the collapsed view — every entity, field, method, and signature, no implementation — always current since it's generated live from `models.py`, not a file to regenerate and re-read. `models.py` is the expanded view, read only when implementation details are actually needed. Load the collapsed view by default; expand only the specific piece you need.

`models_pg.py` holds every Project Gorgon-specific table (`PgPlayer`, `PgNpc`, `PgQuest`, `PgItem`, ...) — split out from `models.py` since it's a large, rarely-needed chunk when working on kb's shared core. Read `models.py` for anything domain-agnostic; only read `models_pg.py` when actually working on pg-specific tables. Any file that imports `Base`/`Item` and registers new tables at import time (alembic's `env.py`, `scripts/dev/check-schema`) must import `models_pg` too, or its tables won't be seen by migrations/schema checks.

Cache stable-but-frequently-referenced facts locally (e.g. game mechanics, reference lore) rather than re-looking them up every time — that's the point of kb. Don't cache genuinely volatile info (stock prices, weather, anything that changes on its own) as if it were a stable fact; look that up fresh when it's needed instead.

## Search

Check `kb search` (see `kb -h`) before writing an ad hoc `kb.py` query — "is X in the wishlist/goals/todos" is exactly what it's for. `kb_cli/search.py`'s `search_entities` is the one substring-search engine (title/description/notes, `ilike`) shared by the per-entity `search` subcommands; the top-level `kb search` additionally calls `Note.search`/`Todo.search`/`Goal.search` for the RAG side (each backed by `HasEmbedding`, see below), since a substring match alone misses phrasing that's topically related but doesn't share exact words — e.g. a Todo titled "build another oil rig" only turns up for a query like "oil rig mushroom base" through the semantic pass, not the substring one.

`HasEmbedding` (`models.py`, applied to `Note`/`Goal`/`Todo`) is the one mixin providing semantic search: two nullable columns (`embedding`, `embedding_model`), a `.search(session, query, **filters)` classmethod (raw `vec_distance_cosine` SQL, filtered to the row's own `embedding_model` so a model upgrade never compares incomparable vectors), and a shared `before_flush` listener that auto-reembeds any dirty instance whose `_embed_fields()` changed — callers never call `.reembed()` themselves after a plain attribute assignment, only each model's own `create()` calls it once for the initial embed before first flush. Adding semantic search to a new model is: inherit `HasEmbedding`, implement `_embed_fields()`/`_embed_source_text()`, call `.reembed()` in `create()`, backfill existing rows once via a one-off `kb.py` script (`for row in sess.scalars(select(TheModel)).all(): row.reembed()`). Measured cost: ~9ms per embed call against the warm server (`kb.service`), so sync-inline embedding on create/update is not a noticeable delay — no background queue needed.

## Inbox

`InboxItem` is for anything whose eventual home isn't known yet — unlike every other kb table, you don't decide up front whether it's a `Todo`, a `Purchase`, a `LogEntry`, or nothing at all. Triage means: create the real record it turns out to be, then `inbox triage` the item. Don't let ideas-in-passing get lost while mid-task — `inbox add` them and keep moving.

`source` (capture channel: `email`, `mobile`, `quick-note`) and `category` (kind of content: `project-idea`, `purchase`) are separate axes — filter `pending` by `category` to triage a large backlog in batches by kind before deciding each item's final home.

## Running commands

`kb.py` (see `kb.py -h`) is the Python-expression runner, a different tool from the `kb` CLI — `kb.py` is for one-off queries/scripts against models directly, `kb` is for the day-to-day subcommands (see `kb -h`).

Bare `kb.py` (no command, `-f`, or `-i`) errors instead of silently dropping into the REPL — always pass `-i` explicitly if you want manual-commit interactive mode.

`sess` and all models are pre-loaded, including game-specific ones (`PgPlayer`, `PgNpc`, `PgQuest`, `PgItem`, ...). No imports needed. Everything shares a single database and session.

`--context NAME` acts in that context for one command only (pre-loaded as `context` in the namespace) without changing the persisted current context — e.g. `./kb.py --context pg.violet "Goal.active(context)"`.

Enum columns take the member (uppercase name, e.g. `Collection.GORGON`), not the lowercase `.value` shown in old muscle memory. `scripts/dev/gen-api` lists valid members per enum.

## Goals, Todos, and Context

`goal show`/`todo show` print a one-line "N history entries" hint when Journal history exists, without dumping it — pass `--history` to expand it inline, or `--history N` for just the last N entries.

`todo pending` always shows Todos from every context; `todo list` scopes to the current context (plus its descendants and no-context Todos) by default, matching `kb summary`'s scoping — pass `--all` to see every context instead.

`Todo.defer_until` hides a Todo from `todo pending`/`kb summary` until that time passes — not a due date, a "don't show me this until it's actually relevant" filter (e.g. "vacuum" deferred to 19:00 today doesn't clutter the view until evening planning time). `todo pending --all` (or `Todo.active(include_deferred=True)`) surfaces deferred-but-not-yet-due items too, for deliberately planning ahead.

### Tags: a Todo (or Goal/Daily/Idea/Timer) that floats to every matching Context

`Context` is a tree (where something is actionable); `Tag` is an orthogonal, flat label for "what kind of place this is" (e.g. `tavern`, `player-shop`) that a `Context` can carry several of (`kb context tag NAME TAG...`). A `Goal`/`Todo`/`Daily`/`Idea`/`Timer` is pinned to exactly one of `context_id` or `tag_id`, never both (`HasContextOrTag` mixin, enforced by a validator) — pin it to a `Tag` instead of a `Context` (`--tag` on `todo add`, mutually exclusive with the global `--context`) when the same real-world action is available at every place carrying that tag, e.g. "buy salt" at every tavern, or "buy medium prisms" at every player-shop. A tag-addressed row then prints under *every* Context carrying that tag in `context tree`/`todo tree` output (duplicated on purpose, since it really is actionable in each place), rather than being pinned to one arbitrarily-chosen location.

`HasContextOrTag.matches_contexts(contexts)` (a classmethod on the mixin, inherited by every model above) is the one expression for "does this row belong to any of these Contexts, directly or via a shared Tag" — every entity's own `.active(session, contexts=...)` classmethod calls it, so `Goal.active`/`Todo.active`/`Daily.active`/`Idea.active`/`Timer.active` all share one tag-fan-out implementation instead of five hand-rolled copies. If a new context/tag-addressable entity is ever added, give it the same `.active(session, context=None, contexts=None, include_no_context=False, ...)` shape (extra kwargs like `Todo.active`'s `effort`/`include_deferred` are fine) so it slots into this pattern rather than becoming a sixth special case.

`kb_cli/context_cmd.py`'s `render_tree` is the one tree-rendering engine behind `kb context tree [--goals|--todos|--dailies|--items|--entities|--ideas]`, `kb todo tree`, and any future `kb goal tree`/`kb daily tree` — each of those commands is a thin call into `render_tree(session, entity_models=(TheModel,), active_kwargs={TheModel: {...}}, scope_to_current=...)`, not a reimplementation. `render_tree`'s `_content_items` always delegates the "is this active/visible right now" decision to each model's own `.active()` (via `matches_contexts`), never to a hand-rolled status/defer_until check in `context_cmd.py` itself — that filtering has exactly one owner per entity, the same way `Daily`'s overdue logic has one owner (see `kb i` engineering node, single-ownership principle). Like `kb context tree`/`kb todo list`, `kb todo tree` scopes to the current context by default; `--all` shows the full tree and also includes not-yet-due deferred Todos (both meanings bundled into one flag, matching `todo list --all`'s "show everything" convention). `kb_cli/timer.py`'s `cmd_tree` is the one exception, still using the older standalone `context_tree.py:render_context_tree` helper, because `Timer`'s tree view needs a custom per-row line (live countdown seconds) that plain `__repr__` doesn't carry — a real display-only need, not filter-logic drift.

SQLite silently drops timezone info on `DateTime(timezone=True)` columns on read-back (the column stores it, but the Python value comes back naive). Every such column is written exclusively through `_now()` (`base.py`), which is always UTC — so a naive value read back from one of these columns is safely known to be UTC, and `.replace(tzinfo=timezone.utc)` should be applied before using it for anything: comparing it, displaying it, or reasoning about it, rather than reading the raw attribute at face value. If a new writer for one of these columns is ever added that doesn't go through `_now()` (e.g. a hand-built local timestamp), fix that writer to store UTC too, rather than adding a special case to how the value is read. SQL-level comparisons (inside a `select(...).where(...)`) aren't affected, only Python-level use after the ORM has already loaded the value.

## Daily

`--recurrence`'s grammar (`daily`, `every:N`, `weekly:MON..SUN`, `monthly:D`) is documented natively via `kb daily add --help`, no need to read `Daily`'s docstring in `models.py` for it. A recurring item has a CLI, same as Goal/Todo/Wishlist; only reach for `kb.py`/`Daily.create(...)` for something the CLI doesn't expose.

## Log and Journal

`LogEntry` is a fact about the world at a point in time (health, events, work log) — not durable reference knowledge (`Note`) and not work with a status (`Goal`/`Todo`). See `LogEntry`'s docstring in `models.py` for the full distinction, and the `Journal` note in the Price/purchase history section below for how `Journal` (structured per-entity history) differs from both.

`Todo.effort` (reusing `WishlistEffort`) marks how much a Todo actually takes — `grab` for something quick/batchable now, `research`/`project` for bigger asks — so `todo pending --effort grab` finds exactly the small stuff worth batching, without it getting lost among everything else.

`Goal`/`Todo`/`Daily`/`Item` all take an optional `context`. `Context` is a real single-parent tree (`parent_id` adjacency list, see `models.py`) — a node's plain leaf name (e.g. `"violet"`, `"levels"`) is unique on its own, with position in the hierarchy expressed through `parent_id`, not by encoding ancestry into the name itself (no more `"pg.violet"`-style dotted names). `kb context tree` prints the current shape.

`context.py` has two distinct entry points for two distinct questions, never conflated: `resolve_context(cli_override=None)` answers "what should a **read**-scoped command (`todo list`, `context tree`, `kb summary`, ...) show me" — with no override it falls back to the persisted current context (`CurrentContext`, shared by every shell/tab — there is no per-shell override), and if `CurrentContext` has never been set it falls back further to the fixed `inbox` Context rather than "show everything" (a fresh session should see a small, known, filtered view, not the entire tree). Every caller must print what it resolved to (`kb_cli._util.scope_to_context` does this for the common case) so the ambient scope is never invisible. `creation_context(args)` answers the different question "what context does a new row from an `add` command get" — it never falls back to the ambient `CurrentContext` at all; with no explicit `--context` it pins the new row to the fixed `inbox` Context directly, so a fresh session can never silently create a record under an unrelated leftover current context. Relocate out of `inbox` later with `kb <noun> update ID --context NAME`. Any script that needs the active context should call one of these two functions, never query `CurrentContext`/`Context` directly.

## Before creating or updating notes

Check for existing related notes first with `notes search` (see `kb notes --help`) — semantic search surfaces related notes even when you don't know the exact title. Use `notes get ID` once you have an id (e.g. from a `kb-<collection>-<id>` pointer), and `Note.find(title)` only once you already know/suspect an exact title (e.g. confirming before an update).

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

## Formatting

`scripts/dev/format [path ...]` runs black over the project (whole project by default).

Enum columns are constrained at the DB level (`Enum(..., create_constraint=True, validate_strings=True)`) — see kb-engineering-10 before adding a new `Enum(...)` column. Adding a new *value* to an existing enum still needs a migration to update the CHECK constraint; use a raw-SQL table recreate (CREATE + INSERT SELECT + DROP + RENAME), not `batch_alter_table`/`alter_column` — see kb-engineering-16 and `alembic/versions/752237ed2641_add_on_hold_to_goalstatus.py` for why and a worked example.

Read kb-engineering-20 before renaming any table's `__tablename__` (e.g. a `PgFoo`->`PgBar` rename): `op.rename_table` renames only the table, never its own PK/UNIQUE/CHECK constraints, so the same raw-SQL table recreate as kb-engineering-16 is needed in the same migration to bring those constraint names in line with what the naming convention now expects. Autogenerate does not flag this drift until a much later, unrelated migration surfaces it as a confusing diff — fix it immediately in the rename's own migration, not later.

Read the newest engineering note on `batch_alter_table` column renames before renaming any column that has a foreign key: a `drop_constraint`/`create_foreign_key` pair issued inside the *same* `batch_alter_table` block as the column rename can silently fail to apply, leaving the FK missing entirely with no error. Put the FK recreation in a separate migration (or separate `batch_alter_table` block) from the rename itself, and always run the throwaway `scripts/db/migrate "verify no-op"` check afterward — that's what actually caught this the one time it happened.

## Price/purchase history

`Vendor`/`VendorItem`/`Purchase` track price and quantity over time for anything transactable, real or in-game — a grocery store and a PG player-shop NPC are both a `Vendor` (`domain="irl"`/`"pg"`), since neither shows a full price history at once, only snippets over time. `Item.upc` is the universal barcode (same everywhere); `VendorItem.vendor_sku` is that vendor's own code for the item (may differ store to store). Look up a scanned/typed code against `Item.upc` first, then `VendorItem.vendor_sku` for that vendor, before prompting to create a new `Item`. Real-world items are `IrlItem(Item, HasWeight)`, matching `PgItem`'s JTI pattern — every `Item` subtype needs its own `polymorphic_identity`, a bare `Item(game="whatever")` with no matching subclass breaks reads.

`Journal` is structured change history for any entity (`entity_type`, `entity_id`, optional `field`/`old_value`/`new_value`/`note`) — distinct from `LogEntry` (a fact about the world, not tied to a record) and `Note` (durable reference knowledge, not history). `journal show ENTITY_TYPE ENTITY_ID` (e.g. `journal show Goal 14`) reads it. Keep a `Goal`/`Todo`'s `description`/`notes` as lean, current understanding — move decision-by-decision history into `Journal` entries instead of letting it accumulate in the record itself.

## Idea

`Idea` is GTD Someday/Maybe — a project idea you like but haven't committed to acting on, distinct from `Todo` (committed next-action work) and `Wishlist` (acquire/purchase, price-bearing). It has no `defer_until`, `priority`, or score, and never appears in `kb summary` beyond a bare count — it's reviewed deliberately (`kb idea list`), not surfaced on its own. Promoting an idea to a real `Goal`/`Todo`/`Wishlist` is a manual relocation: create the new row by hand, `kb idea promote ID --to "..."` to record what it became via `Journal` and mark it resolved — not a live foreign key, so promoted ideas don't leave a permanent cross-reference trail.

## Model

`scripts/model/download` explicitly downloads the embedding model — the only script that hits the network.

## Flashcards

Anki must be closed first (it holds the collection file locked) — `kb anki` waits up to 60s rather than failing immediately if it's still open.

`notetype` accepts a short alias instead of the full Anki name: `reverse`, `reverse-optional`, `type-answer`, or `reverse-type` (a custom note type via `notetype-init`, combining reversed-card generation with forced typed-answer recall in both directions — default to this one for new cards; see Flashcards principle in `CLAUDE_GLOBAL.md`).

`kb anki run` mirrors `kb.py`'s interface (one-shot expression, `-f` script file, `-i` interactive REPL) but pre-loads `col` (the open `Collection`) instead of `sess`+models — Anki auto-saves most mutations itself, so there's no commit step, just `col.close()` on exit.

## Commits

Use `with:<model>` instead of `Co-Authored-By:`.
