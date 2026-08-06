System instructions -- shipped with kb itself, identical for anyone running this project,
never personal to one user. Read via `kb si root`. Distinct from `kb i show root` (that user's own
Instruction tree in the DB: personal context, overrides, and anything they've added) and from
bare `kb` (the routing/GTD-workflow guide, generated from argparse, for humans and LLMs alike).

If a user's `kb i show root` states something that directly contradicts a default here, the user's
instruction wins for that user -- these are defaults, not the only allowed behavior.

PLACEHOLDER: the actual sort of which existing Instruction-tree content (today living in
`kb i show root`, `engineering`, `terminology`, `principles`) is generic-to-anyone versus
personal-to-this-user hasn't been done yet. See the tracking Todo for that work. Once sorted,
the generic content moves here; this file becomes the real system-instruction seed.
