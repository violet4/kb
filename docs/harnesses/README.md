# Harnesses

kb is driven by whatever harness (Claude Code, another agent tool, a plain shell) is running it — kb owns its own content and logic (`kb <noun> <verb>`, `kb hooks <name>`), and each harness supplies only the trigger mechanism to surface it, per `CLAUDE.md`'s harness paragraph. One file per harness here, listing every hook wired up for it in one place — fan out by harness, not by hook, since setting up a harness means finding everything for that harness at once, not hunting per-detector.

A `kb hooks <name>` detector dense enough to need its own explainer (not just a one-paragraph section) gets a standalone doc under `../` instead of living only inside one harness's file — see [`../daily-check.md`](../daily-check.md) for the pattern: the content/rationale lives once, harness-agnostic, and each harness file here carries only its own wiring snippet plus a link back.

- [claude-code.md](claude-code.md) — Claude Code (`~/.claude/settings.json` hooks)

Adding support for a new harness: create `docs/harnesses/<harness>.md` following the same shape (one section per `kb hooks <name>` wired up, a "verify" section, an "adding a new one" section pointing back at `kb_cli/hooks.py`), and add it to the list above.
