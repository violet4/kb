# Daily-check: session-priming lock

Ensures at least one session per day gets primed to run the daily kb routine (`kb summary`, `todo pending`), without interrupting any other session — the earlier-considered alternative, a per-message forcing hook that blocks progress until the daily routine is handled, was explicitly rejected (see kb Goal #28's Journal) because the user values focus/hyperfocus and finds mid-task interruptions disruptive. This doc is harness-agnostic content, per `CLAUDE.md`'s harness paragraph: what the lock does and why lives here once; each harness's own doc (e.g. `harnesses/claude-code.md`) only carries the thin wiring snippet that calls into it.

## Mechanism

`kb hooks daily-check` (`kb_cli/hooks.py`) claims a tmpfs lockfile (`/dev/shm/kb-daily-check.lock`) for the first genuinely new session since the user last slept (or since the last reboot), and prints a priming reminder only for that one claim — every other session opened the same day sees the lock already held by a different session ID and prints nothing. A harness fires this once per new session, not per message (Claude Code's `SessionStart`/`source: "startup"`, not `resume` or `compact` — those aren't a new session starting).

`kb hooks daily-check-release` clears the lock early, handing the daily-check slot to whichever new session claims it next — for when the session that grabbed it turns out to be the wrong one to prime (e.g. it was left open unattended, or the user wants to redo the daily routine somewhere else).

## Sleep detection, not a midnight boundary

Reboot clears the lock for free (tmpfs), matching that sessions here always start fresh (`/kb-persist` at the end of every chat, never a resumed one the next day). But a machine left on overnight, with no reboot in between, needs its own reset signal — and that signal is deliberately a real, multi-hour gap in activity, not a calendar-day rollover, so a late-night-into-early-morning session correctly keeps holding the same lock instead of being mistaken for a new day.

`kb hooks tree-reminder` already fires on every `UserPromptSubmit`-equivalent event, in every session, for its own unrelated purpose (a one-line Instruction-tree re-check reminder) — it doubles as the shared activity heartbeat for this purpose too, stamping `/dev/shm/kb-last-activity` with the current time on every call. `daily-check` frees its lock if that shared stamp is more than 8 hours old, regardless of which session is holding it. This needs no per-session tracking: a single global "was anything happening anywhere" signal is all sleep-detection actually requires, and it's already produced as a side effect of a hook every harness already needs to fire on every message.

A harness that doesn't already have its own equivalent of `tree-reminder` wired to a per-message event needs some other hook wired to `kb hooks tree-reminder` (or a bare touch of `/dev/shm/kb-last-activity`) purely to keep the heartbeat alive — otherwise `daily-check`'s sleep detection can't distinguish "user is idle for a few hours mid-day" from "user went to sleep," since both look like a stale timestamp from a single session's perspective. Do not build a second, harness-specific heartbeat file for this — the whole point of a shared tmpfs file is that any harness's message event, from any session, keeps the one clock alive.

## Wiring a new harness

1. Fire `kb hooks daily-check` once per new session (not per message), piping that harness's session ID on stdin. Print any non-empty stdout as harness-native context/notification.
2. Fire `kb hooks tree-reminder` (or otherwise touch `/dev/shm/kb-last-activity`) on every message in every session, so the shared heartbeat stays current for sleep detection to work.
3. See `harnesses/claude-code.md` for a concrete worked example of both.

## Verify

```bash
echo '{"session_id":"abcd1234","source":"startup"}' | jq -r '.session_id' | /path/to/kb hooks daily-check   # first session today: prints the priming reminder
echo '{"session_id":"abcd1234","source":"startup"}' | jq -r '.session_id' | /path/to/kb hooks daily-check   # same session again: silent (already holds the lock)
/path/to/kb hooks daily-check-release   # clear the lock early
cat /dev/shm/kb-last-activity           # confirm the heartbeat is being stamped by tree-reminder
```

To grab the lock for *this* live session (e.g. after `daily-check-release`, to reclaim it
manually instead of waiting for the next new session), pipe in this session's own ID rather
than a fake one above — Claude Code exposes it as the env var `CLAUDE_CODE_SESSION_ID` (both
the npm and native installs; there is no separate native-only variable, despite that being a
reasonable first guess when something here misbehaves right after switching install methods):

```bash
echo "$CLAUDE_CODE_SESSION_ID" | /path/to/kb hooks daily-check
```

`CLAUDE_SESSION_ID` (no `CODE`) is not a real Claude Code env var — piping a blank line from an
unset var into `daily-check` hits its blank-stdin early return and silently does nothing, which
looks identical to "lock already held by another session" unless the lockfile is checked
directly (`cat /dev/shm/kb-daily-check.lock`) to tell the two apart.
