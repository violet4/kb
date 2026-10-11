title: commit-messages
trigger: when writing a commit message

A commit message is the repository's history record: it explains why the code changed, while the code, its comments, and the current docs explain how things are now (AB632).

Subject: one imperative line, about 50 characters (72 at most), naming what changed. On a rename, name both the old and the new identifier.

Body: required when the reason is not obvious from the diff, an alternative was rejected, something was renamed, moved, split, or removed, or the change has a side effect. After a blank line, give in order: the problem, stated in the present tense; why this approach, and its known shortcomings; each rejected alternative and why it fails; on any rename, move, split, or removal, every old identifier or path with its new one, verbatim (a removal names its replacement, or says there is none); side effects (AB624, AB631). A body that needs many paragraphs means the commit should be split.

Rename a file in its own commit, with no edits in the same commit: git's rename detection needs roughly 50% similarity, so a small file renamed and edited together loses its `git log --follow` history. A move to another repository takes a commit in each repository, each naming the other.

Never put in a commit message: the only copy of how something works now (that belongs in docs or comments), to-do items or status (task record), a debugging diary (a dated record), a link standing in for an explanation, secrets, or detail the diff already shows.

To find what an old name became: `git log --all --oneline --grep='OLD'` and, separately, `git log --all --oneline -S'OLD'` (the two filters combine as AND, so run them as two queries); the matching commit's body names the new identifier or location.
