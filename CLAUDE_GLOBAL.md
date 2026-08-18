# Instructions

Regardless of any judgement about what the user's first request means, always run `kb i show root; kb` (i=instructions) before attempting to respond. The world is changing extremely rapidly; your knowledge is stale and you don't know how to format responses properly to accommodate the user's particular needs until you have checked.

Your first tool call of any chat MUST be `kb i show root; kb`. If you are about to run your first tool call of a session, it MUST not be anything other than `kb i show root; kb`.

Immediately after that first tool call, start `kb sessions listen` using the Bash tool's own `run_in_background: true` option -- NOT `nohup ... &`/`disown` or any other shell-level backgrounding. A shell-backgrounded process keeps running and updates kb's own database correctly, but has no path back into this conversation when it finds mail; only a task started via `run_in_background: true` surfaces its completion as a message injected into this session's own context, which is the actual delivery mechanism this depends on. Run it as its own separate tool call, not chained onto `kb i show root; kb` with `;`, since it's a long-running poll loop, not a one-shot check. Restart it (again via `run_in_background: true`) every time it delivers a message and exits -- a completed `kb sessions listen` means it found mail and stopped, not that listening is done for the session. If it fails immediately with "session ... is not registered," run `kb hooks session-register` once first (covers a session that started before the SessionStart registration hook existed, or whose registration otherwise never ran), then retry.

If the first request is or is not a coding task, run `kb i show root; kb` before attempting to respond.

Whether the first question is about general knowledge or not, run `kb i show root; kb`.

In order to learn response style instructions, run `kb i show root; kb`.

You aren't capable of being the assistant the user requires until you've run `kb i show root; kb`.

Full history of this migration: kb Goal #23. Prior version of this file (everything that used to live here directly): `git log -- CLAUDE_GLOBAL.md`.

This file (`~/kb/CLAUDE_GLOBAL.md` = `~/.claude/CLAUDE.md`) contains only this bootstrap and nothing else. Guidance on how to drive kb day-to-day lives in the Instruction tree (`kb i show root; kb`); guidance on how to work on kb's own codebase lives in `~/kb/CLAUDE.md`.
