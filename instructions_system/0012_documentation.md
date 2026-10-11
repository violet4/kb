title: documentation
trigger: whenever writing, editing, or producing any documentation, write-up, or persistent note-taking -- a doc, README, comment, docstring, report, or deliverable; documentation is very often the primary deliverable of a session, not a byproduct of writing code

Document the reasoning behind a decision -- why this approach and not an obvious alternative --
not a restatement of what's already visible through other means (code structure/naming, a
table of contents, the deliverable's own title). A doc that only re-describes what a reader
could already see adds a maintenance burden without adding information; a doc that captures a
non-obvious constraint, a rejected alternative and why, a workaround for a specific external
limitation, or a synthesis the reader cannot otherwise reconstruct earns its place.

This applies to any documentation deliverable, not only code comments/docstrings: a standalone
report, research write-up, or reference doc is held to the same test -- state the conclusion
and the reasoning that supports it, not a restated inventory of what was searched/read/tried.
When a session produces documentation as its main output rather than as an accompaniment to
code, that doc is still subject to this node, not exempt from it just because no code changed.


A reference doc is a snapshot (root's Snapshots and Records): when what it documents changes, rewrite it to the new state rather than annotating the old one. When writing a record (an incident writeup, a log entry), move what stays useful into the snapshot that owns it at the same time: a lesson that still applies becomes a gotcha with its symptom and cause, an open follow-up becomes a task record, and a decision becomes "X, not Y, because Z." A record never says "still open" or "next." A snapshot links to a record only while the record's finding still holds.