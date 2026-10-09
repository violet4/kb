title: rule-generalization-from-instances
trigger: when writing or editing any persistent rule/instruction text (AGENTS.md/CLAUDE.md, kb si node, style guide) generalized from one or a few concrete examples

Before a rule generalized from a concrete instance persists, run it through five checks, in
order -- an earlier failing check makes the later ones moot. Full checklist, worked example, and
citation trail: ~/agents/docs/model-behavior/rule-generalization-from-instances/README.md (this
project exists to hold durable AI-agent-behavior research backing rules like this one, distinct
from the rule text itself -- see that project's own AGENTS.md).

1. Repeat -- ask the human whether this has actually recurred before, rather than deciding from
memory: a model has no reliable record of its own past sessions and cannot judge recurrence
unaided. If the human confirms this is the first instance and the cost of being wrong once is
low, don't write a standing rule yet -- let it recur or note it ephemerally instead. Even when
unconfirmed, asking is itself useful: it can stop a rule from being written that didn't need to
exist, or surface other instances the human remembers that should shape the rule's actual scope.

2. Rung -- ask why this happened (direct cause), why it wasn't already prevented (system gap),
and where else this same cause could occur (scope); stop the rule at the answer to the third
question, not one rung higher because a broader category came to mind first.

3. Bound -- name a specific adjacent case the rule must NOT cover. If none can be named, the
scope is still too wide. Formally grounded, not just good practice: Gold's theorem (1967) proves
a concept induced from positive examples alone, with no excluded case, is underdetermined --
Angluin's "tell-tale" condition (1980) says the excluded case is what makes the scope
well-posed at all.

4. Separate -- rationale, rejected alternatives, and pre-emptive rebuttals of objections do not
belong inline in the rule text; they go in a docs/ file, kb Journal entry, or memory. The
persisted rule states only the "what," never the "why" or a defense of it.

5. Gate -- before it persists, check it pulls its weight (would removing this line actually cause
a mistake, not just "is the underlying practice bad in the abstract") and that it's verifiable (a
reader with no other context can mechanically check compliance).

No existing named framework covers this end-to-end -- confirmed by three research rounds
(2026-10-09). This checklist is assembled from pieces that do exist: root-cause-ladder technique,
Google style-guide "rules must pull their weight," Gricean Quality/Quantity, policy/standard/
procedure layering, and -- strongest -- classical ML/ILP results (Gold's theorem, Mitchell's
candidate-elimination version spaces) that formally ground the Bound and Repeat steps, not just
heuristic. See the project doc's citation map for which result backs which step.
