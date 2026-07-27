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

Verified: `kb --context grocery todo list` / `goal list` / `idea list` now each print
`context: grocery` (previously silently printed the stale persisted context). `todo
tree --all`, `--include-deferred`, and both together each behave independently. Full
`pytest` suite (24 tests) still passes.
