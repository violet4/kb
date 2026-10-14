title: session-retrospective
trigger: at the end of a major working session (one that changed code, docs, or instructions), or when a review of a session is asked for

A retrospective turns what a session went through into changes to the systems it used, so the next session goes better. Structured debriefs improve later performance by about 25% on average, and the effect depends on four elements: active self-learning, developmental rather than judgmental intent, reflection on specific events, and more than one source of information (AB637). Run it in five steps, with a structure decided in advance (AB637, AB644).

## Ground rules

- Blameless: everyone, the agent included, did the best they could with what they knew and had. A finding names a contributing cause in a process, a tool, or an instruction; for a missed instruction, why it did not reach the session when it applied (AB641, AB640).
- Specific: examine this session's events, not general performance (AB637).
- Successes too: record what worked and why, so it is kept (AB638).
- More than one source: combine the human's observations, the agent's account, and the session's recorded facts; recollection alone is not enough (AB637, AB639).

## 1. Gather the facts

Before interpreting anything, collect what the session recorded (AB644, AB639): the instruction nodes read, and reachable ones left unopened, in every instruction tree in use, not only the one a reminder lists; the records created, changed, and read; the commits made in each repository touched; and every blocked action, failed command, retry, and surprise.

## 2. Ask, in order

1. What was the session meant to do, and what did it do? Where do they differ?
2. What went well, and why? What should be kept?
3. Where was there friction (an error, a retry, a workaround, a surprise), and what contributed to it?
4. Which instructions applied? Which were consulted, which were missed, and why? Which docs were wrong, stale, or misleading?
5. Which commands or scripts were run by hand that a tool should own, and which tool?
6. Which agent instruction files, docs, instruction nodes, tools, or records should change?

## 3. Sweep every system the session touched

The knowledge base and its records, each instruction tree, the shared docs, each touched project's agent instructions file, the tools and libraries used, and the harness's own configuration (hooks, settings).

## 4. Decide and route

Order the findings by resolution distance (root's Resolution-Distance Ordering) and present them for agreement. Then make each finding a change, now, to whatever caused it: code or a command in the owning project, a hook, a test, an agent instructions file, a doc, an instruction node, or a record (AB640). A finding becomes a task record only when its change needs a decision not yet made, or more work than the session has left; a finding with no owner is noted as an observation. The retrospective itself is not recorded: its output is those changes, each carrying its own reason. Follow-through is the step retrospectives most often skip (AB643), so end with the session-handoff pass: commit the changes, record what remains, and report.

## 5. Review the review

Ask whether this method missed something the session showed, or cost more than it returned, and change this node accordingly (AB642).
