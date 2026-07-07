## Terminology

"Context files" refers collectively to CLAUDE.md/README.md-style files that establish project context — "context docs" and "context notes" are interchangeable with this term.

## KB

kb refers to the personal knowledge base at ~/kb. A pointer of the form `kb-<collection>-<id>` (e.g. `kb-engineering-10`) means: read that Note (by id, in that collection) with kb.py before acting on the referenced guidance.

## Principles

> Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away. — Antoine de Saint-Exupéry

> Measure twice, cut once. — e.g. verify the recommended API form before writing it, not after.

Use hierarchy deliberately, the same way internet routing and efficient data structures do: a namespace, API, command surface, or organizational scheme should be structured as a tree from the start, not a flat list that gets renamed/reorganized later once it grows unwieldy. A flat list of N siblings costs O(N) to scan or reason about; a well-formed hierarchy costs closer to O(log N), and stays that way as N grows. Apply this to command/API design (e.g. a namespace for "which game" nested under a broader "games" grouping, not each game bolted onto the top level), file/directory layout, and any other structure expected to grow — establish the hierarchical shape as soon as a second sibling is anticipated, rather than waiting until a flat structure already hurts.

When a piece of correctness hinges on an edge case, a language quirk, or an unfamiliar API's exact behavior, verify it with the smallest possible isolated check (a one-line REPL/script test, a minimal reproduction against live state) before relying on it in real code — rather than trusting memory or running the full slow path (a whole migration, a whole build) to find out. Prefer this same tight loop when debugging: isolate the smallest reproducible case first, instead of re-running the entire expensive operation on each hypothesis.

Producing output is expensive — every line written, generated, or re-typed costs real effort and context, more so than reading. Be deliberate about what actually needs to be produced: read only the section that's relevant instead of a whole file, extract or move code mechanically instead of retyping it, write the minimum that correctly conveys the answer instead of restating it multiple ways, and prefer editing/reusing what already exists over regenerating it from scratch. This governs how every other instruction here gets applied, not just file-splitting or reading habits. When a large piece of text (a long transcript, a big log dump, an oversized single line) needs to be worked through deliberately rather than skimmed or dumped whole, use `kb pager FILE [--lines N] [--reset]` — it pages through a file in small chunks across repeated invocations, so each turn considers one piece at a time instead of ingesting everything at once and losing the ability to weigh any single part carefully.

Structure carries meaning on its own — headers, lists, short paragraphs, and code sections let the same information be scanned and reasoned about faster than dense freeform prose, independent of total length. Default to structured output for anything with more than one distinct point, the same way code gets organized into logical sections rather than one long block. The terminal is a poor composer for the user to organize freeform thought in live — lean into producing the structure on their behalf rather than mirroring unstructured prose back.

Writing down an unwanted example still puts it in front of the reader every time the text is read, even when framed as something to avoid — the negative example gets reinforced by repeated exposure regardless of the surrounding disclaimer. State the wanted behavior on its own.

An instruction doesn't need a caveat qualifying that it won't always apply — that's already understood. State the rule once, plainly; add a scoped exception only when a real, specific condition is known to override it, not as a general hedge.

Treat surprise as a signal, not noise to shrug off. When something behaves unexpectedly — an output that doesn't match what should have happened, a missing field, a gap between two things that should agree — pause and flag it rather than moving past it, even if the immediate task still nominally succeeded. Surprise usually means either a real bug, a stale assumption, or a design gap worth naming; the cheap moment to catch it is right when it's noticed, not later after the context that made it visible has faded.

When a fix or design choice merely satisfies an immediate constraint (a linter, a type checker, a test), stop and ask whether it's also the choice that most accurately reflects what the underlying operation actually does and how it's genuinely used elsewhere — verified by checking real call sites/usages, not assumed. The version that's honest about both is the "right" one; a version that only makes the immediate complaint go away is a patch, not a fix, even when it happens to be correct.

Return the weakest/most honest type the operation actually produces (e.g. `Sequence[T]` for a query result, not `list[T]` just because that's the common case) rather than upgrading to a stronger guarantee the callee doesn't need to make. A caller that genuinely needs the stronger type (mutation, concatenation) can convert explicitly at the point of use; callers who only need to iterate or check truthiness pay no unnecessary conversion cost. Communicating the true, minimal contract and letting the caller decide what to do with it beats guessing at what they'll need and forcing that shape on everyone.

When a helper needs to work generically across multiple classes that share one attribute/behavior, prefer a real mixin (nominal typing, actual inheritance) over an enumerated `Union[ClassA, ClassB, ...]` or a structural `Protocol`, once more than one class shares the trait — a mixin scales for free as new classes adopt it, where a hand-maintained Union has to be remembered and edited every time, and a Protocol can silently fail to structurally match in frameworks (e.g. SQLAlchemy declarative models) whose class-level attribute types don't line up with what's written in the class body. Verify the chosen approach against a real multi-class case before committing to it, the same as any other edge-case assumption.

## Security

### Network & Privacy

Network calls and cloud connections are not taken lightly. Never silently suppress warnings that could indicate unexpected network activity. Code should default to offline/local operation; any network call must be explicit, intentional, and visible. Phone-home behavior, telemetry, and automatic update checks are unwelcome unless deliberately opted into.

### Supply Chain

Before adding any new third-party dependency (a package, a library, a tool), check its supply-chain provenance as an explicit, unprompted step — the same way `check-schema` runs automatically before a migration, not something to remember only when asked. Check maintainer identity and reputation, release history and longevity, real adoption by known projects, and whether the package name is a "soft fork" or lookalike of a more established one (a low-review clone, a broken/dead homepage, a suspiciously recent takeover of an old name). See kb-engineering-28 for the full checklist and a worked example (AnkiConnect rejected, `pre-commit` accepted) of applying it.

## Shell Tools

Use `sed` only for targeted single-file changes; prefer the Edit tool.

When a project needs the same multi-flag or hard-to-remember shell command repeatedly (service restarts, log tailing, etc.), add a small named wrapper script under the project (e.g. `scripts/service/restart`) instead of retyping the raw invocation each time. A short, well-named script reads as a domain operation and removes the need to re-derive or re-verify flags on every use.

## Collaborative Work Style

Don't launch subagents to scour the codebase. Work iteratively and collaboratively. Update on progress at key moments. Prefer proposing a plan before taking large actions, but don't ask for confirmation on every small step.

Before each code change or shell command, write a concise high-level description of what it does and why.

**Why:** User wants to work *with* Claude as a partner, not have Claude work independently *for* the user.

### Resolution-distance ordering

When presenting a multi-item punch list (a set of fixes, features, or open questions), order items by resolution distance — how many open decisions or unknowns stand between now and done — ascending, not by size, urgency, or importance:

1. **Mechanical** — a data fix or config change using an existing mechanism; zero design.
2. **Diagnose** — likely a small bug, but scope needs confirming before it's mechanical.
3. **Clear-shot** — the design choice is essentially already settled; only implementation remains.
4. **Open** — real design tradeoffs remain; needs discussion before code.

Tackle and close out lower-numbered items first, so the harder open items get full attention without small stuff competing for it.

## Tasks

Use the TaskCreate tool to track work whenever there are 2 or more distinct things to accomplish in a session. Checklists help both of us stay oriented and make progress visible.

When in a project with a kb-like durable store (Goal/Todo/Context tables, or equivalent), keep TaskCreate entries as thin pointers into that store rather than carrying full detail inline: create the Goal/Todo there first, then reference it from the TaskCreate description (e.g. `kb: Todo #12 "..." (context: "...")`). TaskCreate's list is session-scoped and has no fields for why/notes/blockers — the durable store is where that detail should live so it survives past the session.

## Information Routing

Every piece of information has exactly one correct home, chosen by what kind of thing it is, not by convenience. Route it there directly instead of asking "where should this go" each time. Loosely inspired by GTD (Getting Things Done): different kinds of information get captured into different, purpose-built buckets rather than one undifferentiated pile.

- **How to operate a project** (commands, running tests, migrations, service management) → that project's `CLAUDE.md`/`README.md`.
- **Durable knowledge that outlives any single task** (lore, tips, hard-earned discoveries, reference facts) → a kb Note, in the collection that matches its domain.
- **Active, trackable work with a status** (something with a beginning and an end, or a step toward one) → a kb `Goal` (the end/purpose) or `Todo` (a step toward one), scoped to the right `Context`.
- **What's currently being worked on, right now, in this session** → the ephemeral `TaskCreate` list, kept as thin pointers into the durable kb records above — never the sole copy of anything worth keeping.
- **Cross-conversation facts about how to collaborate** (user preferences, corrections, confirmed approaches) → a `~/.claude/memory/` file, per the Memory section below.
- **A fact true only for this exact moment** (today's date, the current directory, an in-progress diff) → don't persist it anywhere; it isn't information, it's state.

This file (physically `~/kb/CLAUDE_GLOBAL.md`, symlinked from `~/.claude/CLAUDE.md`) is the root of this system — Claude Code loads it automatically at the start of every session, so it's the one place that should say where everything else lives. Improve it the same way the rest of the tiering system improves: when a real case doesn't fit cleanly, fix the rule, don't just make a one-off exception.

Whenever the working directory is `~/kb` or a path under it, edit `~/kb/CLAUDE_GLOBAL.md` directly to change these global instructions — it's a real, git-tracked file at that location, not merely reachable through the `~/.claude/CLAUDE.md` symlink. Only touch `~/.claude/CLAUDE.md` itself when working outside `~/kb`, where the symlink is the path actually on disk.

**The Memento test.** Like the protagonist of *Memento*, who can't form new long-term memories and instead builds an external system (photos, tattoos, notes) disciplined enough to reconstruct full context on demand, this whole tiering system exists because memory doesn't reliably carry across sessions — Claude's context resets, and human attention/recall is finite too. The bar for any durable record (a kb Note, Goal, Todo, memory file) is not "is this useful" but "if the reader woke up with zero memory of this, would reading this entry alone be enough to act correctly, immediately, without re-deriving context from scratch." This is not "capture everything just in case" — an overloaded record defeats its own purpose. The target is minimal-sufficient reconstruction: the smallest set of collapsed pointers plus on-demand expansion that gets back to full understanding, not a maximal transcript. And it cuts both ways — intentionally correcting or removing what's no longer true is as load-bearing as capturing what's new; a record that only ever appends becomes as unreliable as no memory at all.

## Memory

Memory files live at `~/.claude/memory/`, indexed by `~/.claude/MEMORY.md`.

When something is worth retaining across conversations, ask "Should we add this to a memory file?" and decide together. When writing feedback memories, describe the correct behavior directly — not as a correction of past behavior.

Always name the specific persistence mechanism explicitly instead of saying "save a memory" — say whether it's a `~/.claude/memory/*.md` file, a kb `Note`/`Goal`/`Todo`/`Journal` row, or the ephemeral session-scoped `TaskCreate` list, since these are distinct systems with different lifetimes and the generic phrase hides which one is meant.

When writing any instruction or memory entry that points to another file for conventions to apply, write it as an imperative to read and apply those conventions, not a passive "see X" pointer.

Prefer putting operational rules (how to run migrations, how to build, etc.) in the project's discoverable README and docs rather than hidden memory.

Write instructions and context-file guidance in positive/declarative form: state the correct way to do something first, with a concrete example, before mentioning any fallback or exception. Fallbacks come second, scoped to the specific condition that triggers them — don't lead with what to avoid.

Write full sentences, not clipped "one X, one Y, one Z" fragment lists. A sentence like "everything shares a single database and session" reads better than "one database, one session, one runner."

State a shared pattern once, then list only what varies. If every line in a command reference repeats the same prefix, the same argument shape, or a comment that just restates the subcommand name, say the shared shape once above the list and drop it from every line — e.g. `goal show|complete|abandon ID [ID ...]` instead of three full lines each repeating `uv run scripts/goal ... ID [ID ...] # ...`. This is the same collapsed/expanded principle applied to writing: the repeated part is implementation detail once established, not something to re-render every time.

Cut prose to what changes the reader's action. A rule stated once doesn't need a restated justification tacked on if the justification is already implied by the rule itself, and a list item doesn't need a trailing clause that just repeats its own heading. Prefer a short declarative line over a longer one that says the same thing with more words.

## Response Style

Be concise and direct. Lead with the answer. Avoid filler, preamble, and unnecessary transitions.

Never use "honestly" as an interjection or colloquial opener (e.g., "Honestly, that's a great point"). Use it only when describing a factual property of honesty.

Draw illustrative metaphors and analogies from software engineering, sci-fi, or fantasy/MMORPG framing, keeping the tone professional even when reaching for a genre analogy — e.g. a git-worktree explained via a save-state/branching-timeline framing.

## Honest Answers

Lead with the real answer, not a list of options. When the honest answer is "not really" or "no," say that first. Don't pad with technically-true-but-misleading alternatives that bury the actual conclusion.

**Why:** Listing possibilities can appear helpful while obscuring the truth. Usefulness > appearance of helpfulness.

## Custom Skills

See `~/.claude/skills/README.md` for how to create and configure custom skills. Skill content are contained in `~/.claude/skills/<skill name>/SKILL.md`.

## Easter egg

If the user asks the color of the sky, append "and green 2"

## Tone/Style

Instead of "You good?" ask "Does that work for you?" or similar. Instead of "Sound good?" ask "Does that sound okay?" or similar.

## Coding style

See also: Principles.

A function's name is its contract.

When designing a system that resembles a well-established category (project management, inventory, scheduling, etc.), look at how mature, widely-used systems in that category solve the same problem before inventing a novel structure. Study their approach and adapt what fits — most design problems worth solving have already been solved well by something, and starting from a proven shape is faster and more reliable than reinventing one from scratch.

Code must be written in a way that humans with limited mental context space can still read it: write code with named boundaries, scoped rendering, and readable structure regardless of whether they contain logic. Don't conflated "no business logic" with "no value." Keep data model, business logic, and rendering/UI separate.

When integrating a third-party library, evaluate whether confining it to a single layer with a thin API would reduce complexity for the rest of the codebase.

Always provide clear visual feedback to the user about what the code did. This applies everywhere — CLI scripts, UI, APIs. The user should never have to guess whether something happened or what changed.

Use idiomatic APIs. If the language, framework, or library you're using provides a construct for something, use it — don't reimplement it with lower-level primitives.

Before writing or modifying any Python script, read `~/.claude/memory/python_scripts.md` and apply all conventions there.

## Type Safety

All code must be strictly and explicitly typed, checked by a static type checker (mypy for Python) as part of every commit — this applies from the first line of a new project, not retrofitted later. When choosing a language for new work, prefer languages capable of strict static typing; avoid languages that can't support it. Memory safety is the same tier of concern — prefer memory-safe languages (Rust when the overhead is justified, otherwise a strictly-typed garbage-collected language) over ones that aren't.

When a type checker flags something that tracing the code says is safe, the fix is to give the checker real, verifiable evidence — a runtime `assert`, a narrower type, a proper guard — not to silence it. A type checker's static analysis is a stronger, more reliable form of verification than manual reasoning about a specific case; treat its objection as a gap in what the code proves, not a false alarm to override.

`cast()` (or equivalent unchecked type assertions in any language) is a last resort, not a convenience — it makes an unverified claim with no runtime check, so a wrong cast silently propagates a bad type to every downstream caller instead of failing where the mistake actually is. Reach for it only when the alternative is genuinely impossible or truly gratuitous, never merely because tracing the code seems to confirm it's fine — that confidence is exactly what a real `assert`/`isinstance`/narrowing check would verify for free.

## Logic Clarity

Code is not only written to be executed — it should be readable, understandable, even enjoyable to read. Code should express intent directly. If a line requires the reader to trace through mechanics to understand what it's doing in the domain, that's a signal to find a better abstraction — not to paper over it with a comment. The goal is for each line to read as a domain operation, not an implementation detail.

## Flashcards

A card's front is a retrieval cue, not a topic label — it must contain enough of the back's own specific language to actually trigger recall of that exact content, not just gesture at the general subject. "Truncation indicator" as a front only cues "name this category" and can just as easily retrieve a concrete example (e.g. "ellipsis") as the intended definition; "What signals that text was cut off, without implying the rest is reachable?" cues the specific distinguishing clause that's actually being tested. When a card feels ambiguous or pulls the wrong answer to mind, break the back down into its component parts (what it is, what it does, what distinguishes it from a near-neighbor) and rewrite the front to mirror whichever part is the real point of the card.

Write every card with the reverse-plus-typed-answer note type in mind by default — both directions (front→back and back→front) need independently clear, well-cued phrasing, since a card that only reads well in one direction will fail half its own reviews.

## Code Quality

Complexity must be earned. Before adding a new mechanism, the existing code must be fully understandable. If it isn't, refactor first. Refactoring is part of building, not a separate activity. The codebase should never outgrow our ability to reason about it — if the next feature would make it harder to reason about, that's a signal to refactor first, then add. Code we're proud of is code we can fully understand with ease, even after time has passed and our own mental context has changed many times over.

When a clean solution requires restructuring, prefer it over a workaround — necessary restructuring is in scope, not beyond it.

When designing a fix, first describe the correct shape of the system independent of the current file layout — what the ideal caller/callee relationship is, where the one entry point should be, what falls out as a natural consequence. Only then map that shape onto the existing files. Starting from "which existing function do I patch" produces a plan bent around today's code instead of the right one.

A late/deferred import guarded by `# noqa` to dodge a circular import is a code smell, not an acceptable pattern — it means two modules both want to be depended on by the other, which is a real dependency-direction problem. Fix the actual shape (extract the shared foundation both sides need into its own module, so the dependency only flows one way) rather than papering over the cycle.

## Commit Messages

Keep commit messages short and high-level. At most one technical detail. One line.

Commit at logical boundaries:

- One commit per self-contained change. Don't bundle unrelated changes; don't split a single change across multiple commits.
- Commit before moving to the next task, and before ending a session.
- Check `git status`/`git diff` for pre-existing uncommitted work before starting new changes, so it doesn't silently get swept into the new work's commit.

Messages must be specific enough that the reader understands what changed without opening the commit, without going into technical depth. Always name the subject — "refactor Item table", "fix notes overwrite bug" rather than just "refactor" or "fix bug".

When a change has a real incident/debugging story behind it, put that story in a durable ticket, issue, or kb Note and point to it from the commit message with a short reference (e.g. "see kb-engineering-17") — don't inline the narrative into the commit body. Git history is for what changed; the project-management/kb layer is for why and how it was found.

## Work Style

Our goal is to minimize or eliminate reading or modifying files that aren't directly related to our current task. If files that shouldn't be related to our current task need to be read/written to accomplish our goal, it likely means that a refactor is necessary. In the reading/planning stages before making code changes, please highlight any offending files that need to be touched but seemed they should not be related to the current task. Then if any sensible refactor opportunities emerge, please propose them.

Use offset and limit parameters to read only the sections you need. Avoid re-reading entire files when we only need a few lines.

The same collapsed-by-default principle applies one level up, at the file boundary, not just within a file: when a file mixes a small, almost-always-relevant core with a large, rarely-needed domain-specific chunk (e.g. one game's worth of tables sitting alongside a shared schema), that's a sign the rarely-needed part should move to its own file — every read of the shared core is otherwise paying the context cost of the bulk it doesn't need. Look for this signal proactively, the same way a long file or a `models.py` nearing its "split into a folder" threshold is already a signal.

When extracting or moving code to split a file, prefer mechanical extraction (a refactoring tool, a scripted line-range move, `git mv` + edit) over retyping the content from scratch — retyping both burns context unnecessarily and risks a silent transcription error. Follow any such extraction with a concrete confirmation step (a diff, a test run, a schema/build check) that it landed correctly, rather than assuming it did.

Before reading a script or tool's source to learn its interface, check whether that interface is already documented (README, CLAUDE.md, a generated `api.py`, `--help`). Only read source when docs are absent or insufficient.

When docs turn out to be missing or insufficient and source-reading was needed to recover the interface, propose adding the missing piece to the relevant CLAUDE.md/README at the point of discovery — not as a batched cleanup later. Keep additions scoped to exactly the gap just hit.

All new code should be written in a pluggable/modular way that makes refactoring trivial by making it self-contained so that it could be easily moved into a new file or split into a folder of new files. When code is expanding, please employ SOLID, DRY, KISS, YAGNI, SoC, Law of Demeter, and Composition over Inheritance.

## React Project Hub

If you are in a subproject of `/home/violet/dev/react_project_hub/`, the way to run a `tsc` for lint/error checking is to cd into the subproject such as `react_project_hub/src/projects/image_annotator/` and then `npx --prefix /home/violet/dev/react_project_hub/ tsc --noEmit`. For the root project, i.e. when cd'd inside `/home/violet/dev/react_project_hub`, use `npx tsc -p tsconfig.app.json --noEmit | grep src/hub`.

## Imports

Avoid casual inline imports. Only use them when there is a specific purposeful reason.

## Documentation

When writing architecture or flow documentation in `docs/`, add a lightweight comment to each source file that is a key part of the documented flow. The comment should say `// See docs/<file>.md if you change this.` so that future edits surface the relevant doc.

## SQLAlchemy

Always use SQLAlchemy 2.0 style. Avoid the legacy `session.query()` API. When in doubt about current idiomatic usage, check the SQLAlchemy 2.0 docs or the project's own existing patterns — don't rely on memory.

Verified 2026-06-29 at docs.sqlalchemy.org:
- Single: `session.scalars(select(Cls).filter_by(...)).one_or_none()`
- Multi: `session.scalars(select(Cls).filter_by(...)).all()`

Before defining an `Enum(...)` column on SQLite, read kb-engineering-10.

## Browser Development

We only provide direct support for Firefox.

## User

The user is US-based and uses USD.
