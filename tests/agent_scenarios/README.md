# Agent scenarios

Recorded end-to-end sessions of an LLM agent (Claude Code or otherwise) driving kb
through natural-language requests, kept as a UX regression corpus — distinct from
`tests/*.py`, which asserts code correctness, not experience quality.

Each file is one scenario: the prompt(s) as given, the tool-call path actually taken,
and any friction encountered (wrong output, silent no-op, misleading flag behavior,
missing routing). Write up friction even when the task nominally succeeded — a scenario
that reads clean end-to-end is itself a useful passing case to keep around, so future
changes that regress it get caught.

Not a pass/fail suite to automate (yet) — a growing set of concrete cases to read
before/after changing CLI behavior, and a place to point at when a fix is verified.
