# CLAUDE_GLOBAL.md → Instruction tree migration tracker

Plain, untracked-by-Claude-Code progress log for migrating CLAUDE_GLOBAL.md's sections into
the kb Instruction tree (see Goal #23). Not auto-loaded by Claude Code, so appending here
carries no live-reload notification cost, unlike editing CLAUDE_GLOBAL.md itself mid-session.

CLAUDE_GLOBAL.md stays completely untouched until migration is fully done, then gets replaced
in one single edit by the thin pointer version ("run `kb instructions root`"). Nothing here is
a substitute for CLAUDE_GLOBAL.md's own git history -- it's a checklist, not a copy.

## Sections (## headers in CLAUDE_GLOBAL.md, in file order)

- [x] Terminology → #5 "terminology"
- [x] KB → #5 "terminology" (combined -- both are short, always-relevant definitions)
- [x] Principles → RESTRUCTURED after a placement review: universal/always-true stance (waste-minimization, verify-before-relying, output-is-expensive, treat-surprise-as-signal, structure-carries-meaning + positive-language-from-Memory-section) moved into root (#4)'s own body directly, since these apply regardless of domain and should load in the first read, zero hops -- not gated behind expanding a child. The 5 near-duplicate child nodes were deleted (kb instructions delete, a command that didn't exist until this need surfaced it). #6 "principles" now holds only genuinely domain-conditional items: #8 hierarchy-over-flat-structure, #13 pre-existing-test-not-ground-truth, #14 right-fix-vs-merely-passing, #15 weakest-honest-return-type (triggered), #16 mixin-over-union (triggered), #17 boundary-logic-tables (triggered). Also: #4 (formerly "kb-itself") renamed to "root" and made the single true root node -- previously there were 4 separate root-level nodes (no single root), which broke the "root always loads first" mechanism entirely. terminology/principles/engineering are now root's children, not its siblings.
- [x] Security → #27 "security" (root child, triggered: adding a network call/cloud connection/third-party dependency)
- [x] Shell Tools → #28 "shell-tools" (engineering child, triggered: running shell/Bash commands)
- [x] Collaborative Work Style → #25 "collaborative-work-style" (root child, not folded into root's body -- substantial enough, and specifically about the Claude/user interaction rather than universal stance, to earn its own always-relevant-but-one-hop-away node). Combined with Tasks section (TaskCreate usage) since they're both about how work gets organized in a session.
- [x] Tasks → folded into #25 "collaborative-work-style" (see Collaborative Work Style entry above)
- [x] Information Routing → folded into root (#4)'s body directly, same reasoning as the universal-stance principles: this is referenced by nearly every kb write decision and by /compact-prepare itself, so it belongs in the zero-hop always-loaded read, not a child requiring expansion. The "kb Goal/Todo" and "TaskCreate" and "~/.claude/memory/" rows carried over verbatim (still accurate); the "How to operate a project" row carried over verbatim; added one new row not in the original ("guidance about how a task/topic should be approached -> a node in this tree") since that's a genuinely new information type this tree introduces. The self-referential "this file is the root, symlinked from ~/.claude/CLAUDE.md" framing was NOT carried over verbatim -- rewritten to describe the tree itself as the root instead, since migrating this section is literally replacing what those old sentences described. The Memento test paragraph also migrated here, extended to explicitly include "a node in this tree" as a kind of durable record it applies to.
- [x] Memory → split by universality. Universal writing-discipline lines (full sentences not fragments, state-a-pattern-once, cut-to-what-changes-action) folded into root (#4)'s body, joining the already-migrated positive-language rule. The DRY-pointer rule was already in root verbatim from the Information Routing pass -- confirmed present, not re-added. Memory-mechanism-specific content (where ~/.claude/memory/ lives, when to use it vs. kb, the "name the mechanism explicitly" rule, prefer README over hidden memory for operational rules) → new node #18 "memory-files", triggered ("when deciding whether/how to persist something to ~/.claude/memory/"), placed as a root-level sibling (not under engineering -- it's a cross-cutting persistence-mechanism concern, not a coding topic). Caught and fixed a `kb instructions set-parent` usage mistake here: calling it with no --parent clears the parent entirely (creates an orphan root) rather than being a no-op -- always pass --parent explicitly when re-attaching to a known parent, only omit it when deliberately promoting to root.
- [x] Response Style → folded into root (#4)'s body, joining the existing "how to write and speak" paragraph
- [x] Honest Answers → folded into root's body, same paragraph
- [x] Custom Skills → #26 "custom-skills" (root child, triggered: creating/configuring a skill) -- meta/tooling content, not universal stance, so given its own node rather than folded into root
- [x] Easter egg → folded into root's body (one line, kept as-is per instruction to state it plainly)
- [x] Tone/Style → folded into root's body, same paragraph as Response Style/Honest Answers
- [x] Coding style → #19 "coding-style" (engineering child). "See also: Principles" cross-reference dropped -- no longer needed since these live in the same tree with real parent/child links now, not two separate files needing a manual pointer.
- [x] Type Safety → #20 "type-safety" (engineering child, triggered: writing typed code / type checker errors)
- [x] Logic Clarity → #21 "logic-clarity" (engineering child)
- [x] Flashcards → #23 "flashcards" (root sibling, its own domain unrelated to engineering; triggered: writing/reviewing flashcards). Also added #22 "python-scripts" (engineering child, triggered: before writing/modifying a Python script) as a pointer to the existing ~/.claude/memory/python_scripts.md rather than duplicating its content.
- [x] Code Quality → folded into engineering (#1)'s own body directly, since it's "always true whenever doing engineering work" rather than one narrower sub-topic among siblings -- same reasoning as root's universal-stance content, one level down. The structural-drift-applies-to-instructions-too paragraph (added earlier this session) carried over as part of this.
- [ ] Commit Messages
- [x] Work Style → #24 "work-style" (engineering child)
- [x] React Project Hub → #29 "react-project-hub" (engineering/frontend child, triggered)
- [x] Imports → #30 "imports" (engineering child, triggered)
- [x] Documentation → #31 "documentation" (engineering child, triggered)
- [x] SQLAlchemy → #32 "sqlalchemy" (engineering/python child, triggered)
- [x] Browser Development → #33 "browser-development" (engineering/frontend child, triggered). Skipped 3 stray lines found under this section in CLAUDE_GLOBAL.md ("this is new content added...", "this is another new line...", "this is yet another new line...") -- these are leftover artifacts from the live-reload testing earlier this session (see kb Note #29), not real content, don't migrate them.
- [x] User → folded into root (#4)'s body directly (one line: US-based, uses USD)

RESTRUCTURE (mid-migration, once engineering hit 13 children -- past the ~5-10 fanout target stated in root's own body): added #34 "python" and #35 "frontend" as intermediate grouping nodes under engineering. Moved type-safety/python-scripts/sqlalchemy under python; react-project-hub/browser-development under frontend. engineering back down to 9 direct children.

ALL 27 SECTIONS MIGRATED. CLAUDE_GLOBAL.md has NOT been touched/replaced yet -- per user's plan, back it up first, then swap in the thin pointer version, to test the tree live before committing.

Mark `[x] Section name → Instruction #ID` once migrated. A section split across multiple
nodes lists each: `[x] Coding style → #12 (general), #13 (SQLAlchemy specifics)`.
