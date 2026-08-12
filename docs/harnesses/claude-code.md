# Claude Code

How to wire Claude Code's own hook mechanism (`~/.claude/settings.json`) to this repo's hook scripts. Every hook falls into one of two kinds, per `CLAUDE.md`'s harness paragraph:

- **Harness-agnostic detectors** (`kb hooks <name>`, in `kb_cli/hooks.py`) — plain text on stdin, plain text (or nothing) on stdout, no Claude-Code-specific assumptions. The settings.json entry is a thin adapter that extracts Claude Code's own output into plain text and pipes it through.
- **Harness-specific adapters** (`harnesses/claude-code/*`, this repo) — scripts that read Claude Code's own hook JSON envelope directly (`.cwd`, `.session_id`, `.message`, ...) because what they do is inherently shaped by Claude Code's own event data, not a portable text-in/text-out check. These stay Claude-Code-only but still live in this repo, not `~/bin`, so kb continues to "bring itself along" rather than depending on machine-local scripts a fresh clone won't have.

Every entry is merged into the `hooks` object in `~/.claude/settings.json` (user-global, so it applies across every project — use project `.claude/settings.json` instead only if a hook should be kb-repo-specific). Merge into any existing `hooks` object rather than replacing it — a broken settings.json silently disables everything else in that file.

After editing, run `/hooks` inside Claude Code (or restart the session) to reload — settings.json changes aren't picked up automatically mid-session.

Each harness-agnostic detector's section below covers wiring only — which Claude Code event fires it, what gets piped in on stdin, what the adapter does with non-empty stdout (context vs. deny). What the detector actually checks for and why is content owned by `kb_cli/hooks.py`'s own docstrings (`kb hooks --help`) or, for anything denser, a standalone doc under `../` (see `daily-check` below) — link to those rather than restating them here. A harness-specific adapter (e.g. `notify-claude`) is the one exception: since the script itself only exists for this harness, describing what it does *is* Claude-Code-specific wiring, not a restatement of content that lives elsewhere.

## notify-claude (harness-specific adapter)

`harnesses/claude-code/notify-claude <event-label>` reads Claude Code's own hook JSON payload on stdin (`.cwd`, `.session_id`, `.message`) and builds a plain title/body, tagged with the triggering session/directory — then hands delivery off to `kb notifications send TITLE BODY --priority ...` (`kb_cli/notifications.py`), which owns the actual desktop notification, sound, and `ntfy` push, plus whether any of that fires at all (`kb notifications mute`/`unmute`/`volume N`, persisted in the `Settings` table so it applies across every harness and every future invocation, not just this session). One script backs both events below; the label distinguishes them.

Mute/unmute/volume, independent of any harness:

```bash
kb notifications status            # current mute state + volume
kb notifications mute              # suppress desktop popup + sound (ntfy still fires)
kb notifications unmute
kb notifications volume 50         # 0-100, persisted
```

```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          { "type": "command", "command": "/path/to/kb-repo/harnesses/claude-code/notify-claude waiting" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "/path/to/kb-repo/harnesses/claude-code/notify-claude done" }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb-repo` with this repo's absolute path (e.g. `/home/violet/kb`). Optional env vars: `NTFY_URL` (default `http://localhost:7182/claude-code`), `NTFY_TOKEN_FILE` (default `~/.config/ntfy-token`) — read by the adapter script itself and passed through to `kb notifications send` as `--ntfy-url`/`--ntfy-token-file` so a per-invocation override still works without touching the persisted default.

## mypy-check (harness-agnostic detector)

See `kb hooks --help` / `kb_cli/hooks.py` for what this detects and what it says (points at `kb instructions show 20`, type-safety) — this section is only the Claude Code wiring: pipes a Bash command's combined stdout+stderr through on `PostToolUse`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "hint=$(jq -r '(.tool_response.stdout // \"\") + \"\\n\" + (.tool_response.stderr // \"\")' | /path/to/kb hooks mypy-check 2>/dev/null); if [ -n \"$hint\" ]; then jq -n --arg h \"$hint\" '{hookSpecificOutput: {hookEventName: \"PostToolUse\", additionalContext: $h}}'; else printf '{}'; fi"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`).

## find-root-check (harness-agnostic detector, blocking)

See `kb hooks --help` / `kb_cli/hooks.py` for what this detects and why (a root-scoped `find`). This section is only the Claude Code wiring: pipes a `Bash` command's `.tool_input.command` through on `PreToolUse`, and — unlike `mypy-check`/`tree-reminder`, which only ever add context — the adapter emits `permissionDecision: "deny"` when the detector's stdout is non-empty, instead of always emitting `additionalContext`/`{}`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "reason=$(jq -r '.tool_input.command' | /path/to/kb hooks find-root-check 2>/dev/null); if [ -n \"$reason\" ]; then jq -n --arg r \"$reason\" '{hookSpecificOutput: {hookEventName: \"PreToolUse\", permissionDecision: \"deny\", permissionDecisionReason: $r}}'; else printf '{}'; fi"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`).

## memory-md-check (harness-agnostic detector, blocking)

See `kb hooks --help` / `kb_cli/hooks.py` for what this detects and why (points at `kb instructions show 18`, legacy-claude-code-artifacts). This section is only the Claude Code wiring: pipes a `Write`/`Edit` call's `.tool_input.file_path` through on `PreToolUse`. Same blocking shape as `find-root-check`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "reason=$(jq -r '.tool_input.file_path' | /path/to/kb hooks memory-md-check 2>/dev/null); if [ -n \"$reason\" ]; then jq -n --arg r \"$reason\" '{hookSpecificOutput: {hookEventName: \"PreToolUse\", permissionDecision: \"deny\", permissionDecisionReason: $r}}'; else printf '{}'; fi"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`).

## daily-check (harness-agnostic detector, session-scoped lock)

See [`../daily-check.md`](../daily-check.md) for what this does and why (session-priming lock, sleep detection via the shared heartbeat in `tree-reminder` below) — this section is only the Claude Code wiring. Fires once per new session on `SessionStart`/`source: "startup"` (not `resume` or `compact` — those aren't a new session starting), piping `.session_id` in.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "hint=$(jq -r '.session_id' | /path/to/kb hooks daily-check 2>/dev/null); jq -n --arg h \"$hint\" '{hookSpecificOutput: {hookEventName: \"SessionStart\", additionalContext: $h}}'"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`).

## tree-reminder (harness-agnostic detector, unconditional)

See `kb hooks --help` / `kb_cli/hooks.py` for what this does and why (Instruction-tree re-check reminder, kb Goal #23) and [`../daily-check.md`](../daily-check.md) for its second role as the shared cross-session activity heartbeat used by `daily-check`'s sleep detection. This section is only the Claude Code wiring: takes no stdin, always prints (no detection condition), fires on every `UserPromptSubmit` (no matcher — every single prompt).

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "hint=$(/path/to/kb hooks tree-reminder 2>/dev/null); jq -n --arg h \"$hint\" '{hookSpecificOutput: {hookEventName: \"UserPromptSubmit\", additionalContext: $h}}'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`).

## archive-reminder (harness-agnostic detector, unconditional)

See `kb hooks --help` / `kb_cli/hooks.py` for what this does and why (nudge to snapshot anything from a web search/fetch that actually panned out, without auto-saving — see kb Todo #70 for why auto-save was rejected: a search mostly returns low-quality/SEO/irrelevant hits, and archiving all of them would hoover up the internet instead of the useful subset). This section is only the Claude Code wiring: takes no stdin, always prints (no detection condition), fires on `PostToolUse` for `WebSearch`/`WebFetch`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "WebSearch|WebFetch",
        "hooks": [
          {
            "type": "command",
            "command": "hint=$(/path/to/kb hooks archive-reminder 2>/dev/null); jq -n --arg h \"$hint\" '{hookSpecificOutput: {hookEventName: \"PostToolUse\", additionalContext: $h}}'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/kb` with this repo's `kb` script's absolute path (e.g. `/home/violet/kb/kb`). If a `PostToolUse`/`Bash` entry already exists for `mypy-check`, this is a separate matcher (`WebSearch|WebFetch` vs `Bash`) so it needs its own entry in the `PostToolUse` array, not merged into that one.

## Adding a new one

Harness-agnostic detector (default — prefer this unless the check genuinely needs Claude Code's own event data):

1. Add the detector to `kb_cli/hooks.py` as a new `kb hooks <name>` subcommand — plain text on stdin, plain text (or nothing) on stdout. `kb hooks --help` lists what exists.
2. Add a section here with the matching `PostToolUse` (or other event, see Claude Code's own hook docs) entry that pipes the relevant output through it.
3. If several detectors share the same event/matcher (e.g. more than one `PostToolUse`/`Bash` check), merge them into one hook entry that pipes through each `kb hooks` subcommand in turn, rather than registering the same matcher twice — Claude Code runs all matching hooks, but keeping one entry per matcher here keeps this doc (and the resulting settings.json) easy to scan per-harness rather than per-detector.

Harness-specific adapter (only when the check needs Claude Code's own hook JSON, not just a command's plain-text output):

1. Add the script under `harnesses/claude-code/` in this repo (not `~/bin` or anywhere machine-local) — a fresh clone should get every harness adapter along with kb itself.
2. Add a section here with the matching settings.json entry, using an absolute repo path (`/path/to/kb-repo/harnesses/claude-code/<script>`).

## Verify

```bash
jq empty ~/.claude/settings.json                                                              # valid JSON
jq -e '.hooks.PostToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.type == "command") | .command' ~/.claude/settings.json   # a given hook is present and well-formed -- adjust the path for other events (.hooks.Notification[0]..., etc.)
```

Pipe-test a specific hook's exact command before relying on it — synthesize the stdin JSON a real event would produce and run the command directly, e.g.:

```bash
echo '{"tool_response":{"stdout":"Found 1 error in 1 file","stderr":""}}' | jq -r '(.tool_response.stdout // "") + "\n" + (.tool_response.stderr // "")' | /path/to/kb hooks mypy-check
echo '{"cwd":"/home/violet/kb","session_id":"abcd1234","message":"hello"}' | /path/to/kb-repo/harnesses/claude-code/notify-claude waiting
/path/to/kb notifications send "Test" "hello" --priority high   # exercise delivery directly, bypassing the JSON envelope
hint=$(/path/to/kb hooks tree-reminder); jq -n --arg h "$hint" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $h}}'
echo '{"session_id":"abcd1234","source":"startup"}' | jq -r '.session_id' | /path/to/kb hooks daily-check   # first session today: prints the priming reminder
/path/to/kb hooks daily-check-release   # clear the lock early, e.g. after testing
```
