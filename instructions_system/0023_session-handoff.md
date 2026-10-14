title: session-handoff
trigger: when a piece of work is finished (for example, right after committing it), and before a session's context is lost (the session ends or its context is compacted)

A session's working context does not survive it: the next session has only what this one committed and recorded. At each trigger, leave the work where the next session can resume it without guessing (AB647). At the end of a major session, run session-retrospective first: the changes it routes are what this pass commits and reports.

Commit every finished, verified change, in every repository the session touched. Leave work that is unfinished, untested, or still under discussion uncommitted, and name it in the report with what remains. This pass only adds commits; history that has left the repository is never rewritten (AB645).

Record what exists only in the conversation, each item in the home root's Information Routing gives it: decisions reached; the reasoning behind each non-obvious one; alternatives seriously considered and rejected, with the reason (AB623); findings verified by a test or an observation; caveats raised and not settled. Scan the stretch since the previous pass once per category, since the final conclusions are the most visible and crowd out the reasoning and rejected alternatives behind them. Record only what a future reader needs; a passing remark is not a record. Record without asking first: the report is where the reader objects. Saying that something will be remembered is a claim that it was written down, so write it, and name the record.

End with a short report: each commit and record written, one line apiece, then each item deliberately left out, with the reason in a few words.
