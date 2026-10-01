title: engineering
trigger: at each concrete engineering decision point: writing/editing code, choosing a dependency, designing a schema, picking a pattern, entering a new area of a codebase

General software-engineering discipline: research-grounded practice a competent engineer would apply given adequate time and knowledge, independent of language, project, or personal style preference. Children hold subdomain-specific guidance — expand only what is relevant to the task at hand.

A design must reflect the ideal engineering shape for the problem, not the shape of whatever already exists in the codebase — existing code is one data point about prior intent, not a constraint on what the correct structure is now. Migration cost (renaming, moving files, updating call sites) is not, on its own, a valid reason to choose a worse structure: weigh it only as a tiebreaker between designs that are already architecturally equivalent, never as an excuse to accept avoidable coupling or a worse boundary.
