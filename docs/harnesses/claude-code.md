# Claude Code

How to wire Claude Code's own hook mechanism (`~/.claude/settings.json`) to this repo's hook scripts. Every hook falls into one of two kinds, per `CLAUDE.md`'s harness paragraph:

- **Harness-agnostic detectors** (`kb hooks <name>`, in `kb_cli/hooks.py`) — plain text on stdin, plain text (or nothing) on stdout, no Claude-Code-specific assumptions. The settings.json entry is a thin adapter that extracts Claude Code's own output into plain text and pipes it through.
- **Harness-specific adapters** (`harnesses/claude-code/*`, this repo) — scripts that read Claude Code's own hook JSON envelope directly (`.cwd`, `.session_id`, `.message`, ...) because what they do is inherently shaped by Claude Code's own event data, not a portable text-in/text-out check. These stay Claude-Code-only but still live in this repo, not `~/bin`, so kb continues to "bring itself along" rather than depending on machine-local scripts a fresh clone won't have.

Every entry is merged into the `hooks` object in `~/.claude/settings.json` (user-global, so it applies across every project — use project `.claude/settings.json` instead only if a hook should be kb-repo-specific). Merge into any existing `hooks` object rather than replacing it — a broken settings.json silently disables everything else in that file.

After editing, run `/hooks` inside Claude Code (or restart the session) to reload — settings.json changes aren't picked up automatically mid-session.

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

Detects a failed mypy run in a Bash command's output and reminds to check `kb instructions show 20` (type-safety) — the correct fix for a type-checker error is a real narrowing construct (isinstance, TypeGuard, runtime assert), never `cast()`.

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

Detects a `find` invocation rooted at literal `/` (e.g. `find /` or `find / -name ...`) in a Bash command and blocks it before execution — almost never intended, can exhaust system resources on large trees. Scoped searches (`find .`, `find ./x`, `find /home/user/...`) are unaffected. Unlike `mypy-check`/`tree-reminder`, which only ever add context, this is the first detector that actually denies the tool call: the adapter emits `permissionDecision: "deny"` when the detector's stdout is non-empty, instead of always emitting `additionalContext`/`{}`.

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

Detects a Write/Edit call targeting `~/.claude/memory/*.md` and blocks it before execution, pointing back at `kb instructions show 18` (legacy-claude-code-artifacts). Migration from `~/.claude/memory/` into the kb Instruction tree is DONE (see #18's Journal) -- new durable content belongs in the tree, not a fresh memory file, and in practice the redirect took a manual mention to actually happen rather than being followed on its own. This hook makes that mistake structurally impossible instead of relying on it being remembered. Same shape as `find-root-check`: the adapter emits `permissionDecision: "deny"` when the detector's stdout is non-empty.

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

## tree-reminder (harness-agnostic detector, unconditional)

Injects a short, constant one-line reminder before every user prompt: re-check the Instruction tree for a child relevant to what's about to happen, not just once at session start. Deterministic backstop for kb Goal #23's finding that per-node triggers (e.g. type-safety firing on a real mypy error) don't reliably re-fire mid-conversation from root's own wording alone -- root is read once, at the first tool call of a session, with no built-in re-entry point later. Unlike `mypy-check`, this one takes no stdin and always prints (no detection condition) -- `UserPromptSubmit` has no matcher and fires on every single prompt, so the reminder itself has to be cheap enough to justify appearing every time; kept to one line by design (a longer per-topic checklist was considered and rejected in Goal #23's Journal as too costly per-message).

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
```
