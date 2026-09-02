title: testing-strategy
trigger: when deciding what should be tested, at what level, and how much

A test's value depends on two properties: it must be deterministic (a passing or failing test means the same thing on every run, given the same code), and it must exercise the real contract or invariant it claims to cover, not a convenient proxy for it. A test that passes for reasons unrelated to the correctness it claims to verify — because a dependency was mocked in a way that cannot reflect a real failure mode, for instance — provides false confidence, which is worse than no test, since it actively suppresses the signal that would otherwise prompt verification.

What to test, and at what level (a single function in isolation versus an integration across real components), is itself a design decision to make deliberately per case, not a fixed ratio applied uniformly — the deciding question is which level of test would actually catch the failure mode that matters for the code in question.
