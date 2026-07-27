# Scenario: "what do we need at the grocery store?"

## Prompt
> what do we need at the grocery store?

## Expected ideal path
Resolve "grocery store" to the `grocery` Context (and its children `safeway`/`winco`),
list pending Todos scoped to just that subtree, answer directly.

## Actual path taken
1. `kb search grocery` / `kb search "grocery store"` — found the `grocery` Context but
   otherwise only semantic noise (unrelated Notes/Todos/Goals ranked by embedding
   distance, nothing grocery-specific).
2. `kb --context grocery todo list --all` — `--all` turned out to mean "show the whole
   tree, not just current context," not "include deferred items in this context" as
   assumed. Returned todos from unrelated contexts (`levels`, `palworld`, `timer`, ...).
3. `kb --context grocery todo list` (no `--all`) — printed `context: palworld` and then
   listed `palworld`-scoped todos, i.e. **the `--context grocery` override was silently
   ignored** and the persisted current context (`palworld`) was used instead.
4. `kb context tree --todos --all` + manual grep for `grocery`/`safeway`/`winco` — this
   is what actually worked: confirmed no pending Todos exist under `grocery` or either
   of its children.

## Friction / bugs found
- **`--context NAME` global override appears not to affect `todo list`'s scoping** —
  output still showed `context: palworld` (the persisted current context) instead of
  `grocery`. Per `~/kb/CLAUDE.md`, `--context` should resolve once and be forwarded to
  any subcommand that accepts a context. Needs a repro under `scripts/dev` or a unit
  test to confirm whether this is real or an artifact of arg placement.
- **`todo list --all`'s two meanings collide with expectations formed from `todo tree
  --all`.** `todo tree --all` means "show full tree + not-yet-due deferred items"
  (documented, intentional per CLAUDE.md). `todo list --all` was assumed to mean the
  same "include deferred" sense but actually means "ignore current-context scoping
  entirely" — same flag name, different-enough behavior across sibling commands that
  it produced a wrong mental model mid-session.
- No single command answers "what's pending under Context X and its descendants" in
  one shot without falling back to grepping a full `context tree --todos --all` dump.
  `kb --context X todo list` is supposed to be exactly this, per point above.

## Resolution
Fixed. Root cause: the top-level `kb` entry point already resolves `--context` once
into `args.context` (a real `Context` object) before dispatch and threads it to every
subcommand — this part worked as documented. But `todo.py`, `goal.py`, and `idea.py`'s
`cmd_list` each called `resolve_context(args.session)` a second time, with no override
argument, silently re-deriving from the persisted `CurrentContext` instead of using the
already-resolved `args.context` — three independent copies of the same copy-paste bug,
not three separate issues.

Fix: replaced `current = resolve_context(args.session); in_scope =
scope_to_context(args.session, current)` with `in_scope = scope_to_context(args.session,
args.context)` in all three files (`scope_to_context` already existed in `kb_cli/_util.py`
and already does the right thing — it was just being bypassed). Removed the
now-unused `resolve_context` import from each. No new plumbing needed: `args.context`
was already the shared, pre-resolved filter object every subcommand should have been
pulling from — the fix was deleting redundant re-resolution, not adding propagation.

The `--all` flag naming collision on `todo tree` (previously bundling "ignore scoping"
and "include deferred" into one flag) is also fixed: `todo tree --all` now means only
"show the full tree, not just current context," matching `todo list --all`'s single
meaning; the deferred-inclusion half moved to its own new `--include-deferred` flag,
independent of `--all` (pass both together for the old combined behavior). Considered
and rejected pushing `--all` to the top-level `kb` parser, or folding it into
`--context` as a magic `--context all` sentinel — `--all` only makes sense on
`list`/`tree`-shaped read commands, not `add`/`update`/`show`, so it doesn't meet the
bar for a global flag the way `--context`/`--as-of` do; and "all" isn't a Context name,
so overloading `--context` with a sentinel string would just reintroduce per-subcommand
special-casing of the kind just removed. `todo pending --all` (means "include deferred,"
no scoping concept there) and `todo search --all` (means "include done/dropped") were
left as-is — each already has one single, subcommand-appropriate meaning; only `tree`
was bundling two unrelated meanings into one flag.

**Follow-up (caught on re-test):** the `--all` split above was only applied to
`cmd_tree`, not `cmd_list` — `cmd_list`'s `--all` branch still called
`Todo.active(args.session, effort=effort, include_deferred=True)` with no `contexts=`
filter, i.e. still bundled "ignore scoping" with "always include deferred," and its
non-`--all` branch also always passed `include_deferred=True` regardless of any flag.
Re-running this exact scenario after the first fix reproduced identical output,
confirming `cmd_list` was never actually touched despite the commit message describing
the split as flag-name-collision-resolved project-wide. Fixed by applying the same
`--include-deferred` flag to `p_list`/`cmd_list` that `p_tree`/`cmd_tree` already had,
so both branches of `cmd_list` now pass `include_deferred=args.include_deferred`
instead of a hardcoded `True`.

Verified: `kb --context grocery todo list` / `goal list` / `idea list` now each print
`context: grocery` (previously silently printed the stale persisted context) and, after
the follow-up fix, return exactly the 4 grocery/safeway/winco todos plus no-context
todos — not the full unscoped list. `todo tree --all`, `--include-deferred`, and both
together each behave independently, and `todo list` now matches. Full `pytest` suite
(24 tests) still passes.

**Second follow-up (audit of sibling `cmd_list`s):** since the original bug was three
copy-pasted `resolve_context` calls across `todo.py`/`goal.py`/`idea.py`, checked both
siblings for the analogous `--all`-bundling issue found in `todo.py`. `idea.py`'s
`--all` was already clean (single meaning: ignore scoping; status filter always
ACTIVE, unaffected by `--all`). `goal.py`'s `--all` bundled two unrelated axes: ignore
context scoping, *and* silently drop the default ACTIVE-only status filter when no
`--status` was given — the second half undocumented in `--help`. Fixed by making
`--all` scoping-only in all three `cmd_list` branches (ACTIVE via `Goal.active(session)`
with no `contexts=`, and the explicit-non-ACTIVE-status branch now applies
`Goal.matches_contexts`-based scoping unless `--all` is passed, instead of always
returning every status globally). `--status` now controls which statuses are shown
independently of `--all`, matching the todo fix's principle of one flag per axis.
Verified all four `--all`/`--status` combinations independently; `pytest` suite (24
tests) still passes.

**Third follow-up (search never honored --context at all):** `kb search`/`kb todo
search`/`kb goal search` were unconditionally global — `search_entities` in
`kb_cli/search.py` had no context parameter, so the global `kb --context NAME search
...` override, while correctly resolved into `args.context` by the top-level `kb`
entry point, was silently dropped by every search command specifically (`list`/`tree`
read it; `search` never did). This meant the original scenario's actual best path —
"resolve grocery store to the grocery Context, then search/list scoped to it" — had no
single command that did both at once for a substring query; only the eventual
`context tree --todos --all` + grep workaround did. Audited every other `cmd_list`-less
command for the same gap: `daily list`/`kb summary` intentionally never scope Dailies
by context (matches `Daily.due()`'s signature, which has no context param at all --
dailies are meant to always surface regardless of location), and `wishlist search` has
nothing to scope by since `Wishlist` isn't `HasContextOrTag`. Only `search.py` had a
real gap. Fixed by giving `search_entities` an optional `context` param: when set, it
additionally restricts any `HasContextOrTag` model's rows (via `Goal.matches_contexts`,
the same helper `list`/`tree` already use) to that context's subtree plus no-context
rows, leaving non-context-addressable models (`Wishlist`, `Context` itself) unaffected.
`cmd_search`/`cmd_search_all` now pass `args.context` through only when
`args.context_explicit` is true, so search stays unscoped by default (preserving its
"find X regardless of location" purpose) and only narrows when the global `--context`
flag is actually passed.

**Fourth follow-up (semantic search closed the same gap):** the semantic
(embedding-based) `Note.search`/`Todo.search`/`Goal.search` calls inside
`cmd_search_all` were initially left unscoped, since `HasEmbedding.search` runs a raw
SQL `vec_distance_cosine` query with only equality `filters` (e.g.
`collection=Collection.ENGINEERING`), which can't directly express the OR-based
context/tag scoping `matches_contexts` needs at the SQL layer. Revisited given kb is
still under active development and the point of this exercise is smoothing out real UX
friction, not stopping at "the substring half is fixed, good enough." Fixed by adding
an optional `context` param to `HasEmbedding.search` (`models.py`): when given, it
widens the SQL candidate set (10x limit, capped at 200) so scoping doesn't just leave
fewer than `limit` results, resolves the context's subtree via
`Context.self_and_descendants`, and re-filters in Python using the same
context_id/tag_id/no-context logic `matches_contexts` expresses in SQL, before
truncating back to `limit`. `Note` is untouched (not `HasContextOrTag`, correctly
unscoped); `Todo.search`/`Goal.search` calls in `cmd_search_all` now pass `context=`
through from `args.context` (same `context_explicit`-gated value as the substring half).

Verified: `kb --context grocery search buy` now returns exactly the 4
grocery/safeway/winco todos in *both* the substring-search section and the semantic
Todos section (previously the semantic section still leaked `buy salt`/`buy medium
prisms` from unrelated Serbule Keep/player-shop contexts even when `--context grocery`
was passed) — this is now the single command that fully answers the scenario's
original question end to end, replacing the `context tree --todos --all` + grep
workaround. `pytest` suite (24 tests) still passes.

**Fifth follow-up (re-running the exact scenario still took the scenic route):**
re-ran "what do we need at the grocery store?" fresh after all four fixes above. The
correctness bugs were gone — no wrong-context, no leaked unrelated todos — but the
path taken still tried `todo pending --all` and `context tree --todos` first, missed
both, then finally landed on `kb --context grocery todo list`, never tried
`kb --context grocery search buy` at all. The fixes made the right command *work*, but
nothing in the routing guide said which command to reach for first, so an agent with no
memory of this session had no way to know the single-shot scoped command existed.
Root cause: `kb`'s own routing guide (in the `kb` script's `_BARE_INSTRUCTIONS`) had a
write-side rule ("tied to a place -> pin it with --context on add") but no matching
read-side rule ("a question about a place -> read it back with --context"), so the
guide itself pointed an agent at the write pattern only, leaving the read pattern to be
rediscovered by trial and error every time. Fixed by adding a read-side mirror
immediately after the existing write-side --context paragraph in the `kb` script,
naming the exact commands (`kb --context X search QUERY`, `kb --context X todo list`)
and using this scenario's own query as the worked example, so future agents hit the
one-shot command on the first try instead of re-deriving it. Verified `kb -h`/bare `kb`
still parse and render correctly; `pytest` suite (24 tests) still passes (routing text
isn't unit-tested, this is a documentation-only change).
