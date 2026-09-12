# Instructions

Regardless of any judgement about what the user's first request means, your first tool call of any chat MUST be `kb si show root`, and your second tool call MUST be bare `kb` (i=instructions) -- two separate tool calls, not one chained with `;`. The world is changing extremely rapidly; your knowledge is stale and you don't know how to format responses properly to accommodate the user's particular needs until you have checked. Two separate calls because each command's own output must independently stay well under the Bash tool's own truncation threshold (see kb Note #210) -- chaining them into a single call risks pushing their combined stdout over it even when each command's own output alone is safely sized.

If the first request is or is not a coding task, run `kb si show root` and bare `kb` before attempting to respond.

Whether the first question is about general knowledge or not, run `kb si show root` and bare `kb`.

In order to learn response style instructions, run `kb si show root` and bare `kb`.

You aren't capable of being the assistant the user requires until you've run `kb si show root` and bare `kb`.

Full history of this migration: kb Goal #23. Prior version of this file (everything that used to live here directly): `git log -- CLAUDE_GLOBAL.md`.

This file (`~/kb/CLAUDE_GLOBAL.md` = `~/.claude/CLAUDE.md`) contains only this bootstrap and nothing else. Guidance on how to drive kb day-to-day lives in the Instruction tree (`kb si show root`, `kb`); guidance on how to work on kb's own codebase lives in `~/kb/CLAUDE.md`.
