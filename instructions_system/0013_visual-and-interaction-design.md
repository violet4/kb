title: visual-and-interaction-design
trigger: when writing, building, or modifying a user interface

An interactive control must be placed adjacent to the content it acts on, not merely aligned with it via a layout convention (e.g. flexbox `space-between` pinning a label left and its action right). Proximity is the interface's only free signal of relatedness; splitting label and control to opposite edges of a container erases that signal even when the visual result looks tidy.

This has established names, useful for diagnosing and for justifying a fix in review:

- Gestalt law of proximity: elements near each other are perceived as related, and elements far apart are perceived as unrelated, independent of their actual logical relationship. Common region (shared border/background) is the sibling principle for grouping by enclosure instead of distance.
- Fitts's Law: time to acquire a target grows with the distance to it and shrinks with its size. Placing a control far from the content that motivates clicking it maximizes acquisition cost for both pointer and eye, and disproportionately burdens motor-impaired and switch/head-pointer input — this is an accessibility defect, not merely an aesthetic one.
- Split-attention effect (Cognitive Load Theory): when two pieces of information a person must integrate are separated in space, working memory must hold one while searching for the other, adding load that contributes nothing to the task itself.
- Scan path / saccade cost: each eye movement between fixations has a measurable cost; a layout that forces long horizontal saccades to reconnect a label with its control fights natural reading scan patterns (see NN/g's eye-tracking research on F-pattern/Z-pattern scanning) instead of working with them.

A row's actions belong inline with its subject, in a fixed-width cluster immediately adjacent to it, not right-aligned to the container edge merely because that produces a visually symmetric two-column layout. Visual symmetry and task efficiency are different objectives; a layout can satisfy the first while actively working against the second.


Conditionally-rendered content (an error message, an inline confirmation, a loading state) must not shift the position of unrelated content around it when it appears or disappears. This is cumulative layout shift (CLS) — a Core Web Vitals metric quantifying this — and it is disorienting because it invalidates the reader's just-formed spatial model of the page at the moment they're acting on it (e.g. clicking a second time right where a related control used to be). Reserve space for the transient content in advance (a fixed or minimum height on its container) so its appearance is a content change, not a reflow, rather than only rendering it when present.
