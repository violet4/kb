# Sources

Citation rollup for research grounding the instructions_system/ tree. Each entry: id, title, URL, and which node(s) it grounds. Individual node bodies also carry inline citations where a claim is directly attributed; this file is the index, not a replacement.

- AB409 — SWEBOK v4 / SFIA9 Guide — https://sfia-online.org/en/tools-and-resources/bodies-of-knowledge/swebok-software-engineering-body-of-knowledge/swebok4-sfia9-the-guide-to-the-software-engineering-body-of-knowledge — grounds the engineering subdomain taxonomy (root's 10 hub children; see Note #287).
- AB410 — AWS Well-Architected Framework: The Pillars — https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html — grounds the taxonomy, independent cross-check against SWEBOK.
- AB411 — CircleCI engineering competency matrix — https://progression.fyi/f/circle-ci — grounds the taxonomy against real practicing-org leveling structure.
- AB412 — GitLab Handbook: Architecture Design Documents — https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/ — grounds system-architecture-and-design as a distinct real-org discipline.
- AB413 — Google Engineering Practices: Code Review Guide — https://google.github.io/eng-practices/review/ — grounds design/complexity/testing/naming as separate review dimensions in the taxonomy.
- AB414 — SEBoK: Overview of the SWEBOK Guide — https://sebokwiki.org/wiki/An_Overview_of_the_SWEBOK_Guide — independent cross-check on SWEBOK's structure.
- AB415 — Brendan Gregg, "Thinking Methodically about Performance," ACM Queue (2013) — https://queue.acm.org/detail.cfm?id=2413037 — grounds system-level-performance's "measure, don't guess" / structured-methodology claim.
- AB416 — Donald Knuth, quote on premature optimization, via Wikiquote — https://en.wikiquote.org/wiki/Donald_Knuth — grounds system-level-performance's full (often-misquoted) framing of when optimization is and is not warranted.
- AB417 — web.dev, "Performance budgets 101" — https://web.dev/articles/performance-budgets-101 — grounds system-level-performance's "state the expectation before building" claim.
- AB418 — "Don't repeat yourself," Wikipedia, summarizing Hunt & Thomas, *The Pragmatic Programmer* (1999) — https://en.wikipedia.org/wiki/Don%27t_repeat_yourself — grounds code-level-implementation's reuse-before-reimplementation rule.
- AB629 — Shi et al., "Large Language Models Can Be Easily Distracted by Irrelevant Context," ICML 2023 — https://arxiv.org/abs/2302.00093 — grounds root's Snapshots and Records: irrelevant loaded context degrades accuracy.
- AB630 — Liu et al., "Lost in the Middle," TACL 2024 — https://arxiv.org/abs/2307.03172 — grounds root's Snapshots and Records: accuracy drops as relevant content is buried in long context.
- AB626 — Chroma, "Context Rot" (2025) — https://www.trychroma.com/research/context-rot — grounds root's Snapshots and Records: a single distractor measurably degrades performance.
- AB625 — NARA, archival appraisal conclusions (Schellenberg, primary vs. secondary value) — https://www.archives.gov/research/alic/reference/archives-resources/appraisal-conclusions.html — grounds root's Snapshots and Records: what history is worth a record.
- AB624 — git, SubmittingPatches — https://git-scm.com/docs/SubmittingPatches — grounds commit-messages: body content, rejected alternatives, present tense.
- AB631 — Linux kernel, "Submitting patches" — https://www.kernel.org/doc/html/latest/process/submitting-patches.html — grounds commit-messages: problem, impact, tradeoffs; one problem per patch.
- AB632 — Simon Tatham, "Commit messages" (2024) — https://www.chiark.greenend.org.uk/~sgtatham/quasiblog/commit-messages/ — grounds commit-messages: the commit describes the change, code and docs describe the current state.
- Gold, E. M., "Language identification in the limit," Information and Control 10(5), 1967 — grounds rule-generalization-from-instances' Bound step: a concept learned from positive examples alone is underdetermined.
- Angluin, D., "Inductive inference of formal languages from positive data," Information and Control 45(2), 1980 — grounds rule-generalization-from-instances' Bound step: a named excluded case (tell-tale) makes the scope well-posed.
- AB633 — Microsoft MSRC, "A proactive approach to more secure code" (2019) — https://msrc.microsoft.com/blog/2019/07/a-proactive-approach-to-more-secure-code/ — grounds type-safety: about 70% of Microsoft's CVEs each year are memory-safety issues.
- AB634 — Chromium Security, "Memory safety" — https://www.chromium.org/Home/chromium-security/memory-safety/ — grounds type-safety: about 70% of Chromium's high-severity security bugs are memory-safety bugs.
- AB635 — CISA et al., "The Case for Memory Safe Roadmaps" (2023) — https://www.cisa.gov/resources-tools/resources/case-memory-safe-roadmaps — grounds type-safety: government agencies recommend memory-safe languages.
- AB636 — Gao, Bird, Barr, "To Type or Not to Type: Quantifying Detectable Bugs in JavaScript," ICSE 2017 — https://earlbarr.com/publications/typestudy.pdf — grounds type-safety: TypeScript and Flow each detect about 15% of sampled public JavaScript bugs.
