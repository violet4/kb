"""Bare `kb`'s routing-guide text, extracted so it's importable both by the top-level `kb`
entry point (which prints it) and by kb_cli/stats.py (which needs the exact text to estimate
its token cost) without either one shelling out to the other -- see kb Note #148."""

# Bare `kb` (no args): short, instructional orientation -- "how do I use this right now."
# `kb -h`: full technical reference -- every flag, every subcommand, what CONTEXT/--as-of
# actually mean under the hood. Two tiers, not duplicated content -- bare kb points at -h for
# depth rather than repeating it, same DRY-pointer discipline as the Instruction tree itself.
BARE_INSTRUCTIONS = """\
## Routing

Information a project owns goes in that project (its own docs, organized by its own domain);
kb is for what has no other home.

Routing a plain statement to the right subcommand (the noun -- which table):
  A stated fact/observation about the world -> log
  A piece of completed work not tied to an existing Todo/Goal (nothing was ever "pending") -> win add CONTEXT TITLE [BODY]
  Claude used a phrase or showed a habit worth flagging for later analysis -> flag CONTEXT NOTE (see kb Goal #41)
  A stated need/intent, not yet done -> todo
  Existing behavior that's wrong (a defect/regression, not just unfinished work) -> bug
    (same table/lifecycle as todo, just kind=bug -- `kb bug add/list/pending/...` mirrors
    every `kb todo` subcommand with --kind fixed to bug; `kb todo add --kind bug` also works)
  A bigger purpose/end-goal, or multi-step work -> goal
  A decision/change to an existing record -> journal add ENTITY_TYPE ID NOTE
    (this is what `show`'s "N history entries" hint refers to -- Journal entries are
    hidden by default on `show`, pass --history to expand them inline)
  Durable reference knowledge (not tied to a task) -> notes add CONTEXT TITLE BODY
  Something to buy/acquire, price-bearing -> wishlist add CONTEXT TITLE
  An idea you like but haven't committed to -> idea
  A URL worth keeping a snapshot of -> ab add URL TITLE REASON (title+reason required, see below)
  A relationship between two existing records (any tables) -> link add TYPE:ID TYPE:ID --relation "..."
  Unsure where it goes -> inbox, triage later

Once you have the right noun, most subcommands share the same small set of verbs -- this is
the shape, not per-command trivia, so it isn't repeated per row above: `add` creates a new
record; `show ID` reads one; `update ID` edits one in place; `complete ID` (or a closer verb
like `abandon`/`drop`/`activate` where one genuinely fits better) resolves one. A stated fact
usually means `add`; "I finished/fixed/no longer need X" usually means `complete` or `update`
on an EXISTING record, not a fresh `add` -- check `kb <noun> pending`/`list`/`search` for the
existing record first rather than creating a duplicate. Run `kb <noun> --help` to see the real
verb set for that noun; it isn't identical everywhere.

## Context: Every Record Has a Home

Every `add` takes where the record belongs as its first argument, CONTEXT: a context name, or
#TAG for a record that floats to every context carrying that tag. Example: "I need salt next time
I'm in Serbule Keep" is `kb todo add "serbule keep" "buy salt"`, not a title that mentions the
place in passing; "buy salt at any tavern" is `kb todo add "#tavern" "buy salt"`. When the right
home is genuinely unclear, `inbox` is a real context for "file it later" -- type it explicitly.
Notes, log entries, and wishlist items take a context only, not a tag.

An unknown name is an error that lists close matches and the `kb context add NAME --parent P`
command; nothing creates a context implicitly. Check `kb context tree` before creating one, so a
new context lands under the right parent instead of at the top level. Move an existing record
with `kb <noun> update ID --context NAME`.

A question about a place ("what do we need at X", "what's pending at X") is the read-side mirror:
`kb search --context X QUERY` (substring plus semantic, scoped to X's subtree) or
`kb todo list --context X` (everything pending under X, no query needed), not
`context tree`/`todo pending --all` plus manual grepping. On read commands, --context NAME goes
after the command, like any other flag, and narrows to that context and its sub-contexts. Every
scoped command prints which context it resolved to (`context: grocery`).

The one global flag is `--as-of WHEN`, which comes right after `kb`: `kb --as-of 19:00 daily
list` runs the command as if it were that time.


## Writing Long Text

Write any body/description/note longer than a short sentence through stdin, not as an inline
shell argument: pass `-` as that argument's value and pipe or heredoc the real content in, e.g.
`kb notes add CONTEXT "title" - <<'EOF'` ... `EOF`, or `some_command | kb notes add CONTEXT "title" -`. This is
the default for real content, not a fallback reserved for text with backticks/`$`/quotes in it --
inline arguments force every write to first predict whether the shell will reinterpret something
inside the text, and a multi-paragraph body is exactly where that prediction is easiest to get
wrong. The quoted heredoc delimiter (`<<'EOF'`, not `<<EOF`) is what makes this fully safe:
quoting the delimiter turns off all shell expansion inside the block, so backticks, `$(...)`,
`$VAR`, and literal quotes all pass through byte-for-byte with zero escaping to get right by
hand. Every `add`/`update` subcommand taking a free-text positional or `--body`/`--description`/
`--notes`/`--reason`-style flag accepts `-` this way. Only one `-` stdin read is possible per
invocation (stdin can only be consumed once) -- for a command with two free-text args (e.g.
`ab add URL TITLE REASON`), pass `-` for whichever one is actually long and give the other as a
normal short inline string.

## Linking Records

Default to several small linked records over one large one: the moment a record would cover
more than one reason someone might come looking for it, split it and connect the pieces with
`kb link add` instead of writing one combined record — a link costs one command and makes each
piece independently reachable, so there's no size/completeness tradeoff to weigh before
reaching for it. `kb link add A B --relation "..."` links any two existing rows in any tables, each given as
TYPE:ID (e.g. `kb link add Goal:34 Todo:102 --relation "tracked-by"`) -- TYPE is the record's
own model name (Goal, Todo, Note, ...) and ID its numeric id. `--relation` reads strictly
A-to-B and is stored exactly as given, never reordered: `Goal:34 --tracked-by--> Todo:102`
means "Goal 34 is tracked by Todo 102," not the reverse -- put the grammatical subject of the
relation first (A), the object second (B); if in doubt, read the args back as a sentence
("A [relation] B") before running the command. `--relation` is required and must be a
non-empty label; both endpoints are validated to actually exist before the link is written, so
a link can never point at a nonexistent row. `kb link add` prints the created link's own `#ID`
in its output -- `kb link rm ID` takes that id, never guess or reuse an id from an earlier
link. `kb link show TYPE:ID` renders the graph outward from that row, one hop deep by default
(`--depth N` to go further -- start with 1, since link-dense areas of the graph can expand into
a large subgraph fast at 2+ hops). Run `kb link -h` for rm and the full picture.

## Archiving URLs

`kb ab add URL TITLE REASON` snapshots a URL -- TITLE (neutral, what the page is) and REASON
(why it was worth keeping) are both required, never optional, so nothing gets saved as a bare
link with no record of why it mattered. Save freely, err toward over-saving: e.g. a vendor's
current privacy/telemetry policy page is worth a snapshot (it reflects a moment-in-time
belief/policy that could later change), a doc page consulted just to fix one env var isn't.
Prints the row's id as ABn (e.g. "AB23") -- embed that exact token in whatever Note/Todo/
Journal body cites the URL (e.g. "Sources: AB23"), not the bare URL alone, so the citation
travels with the prose. Run `kb ab -h` for the full picture (list/show, ArchiveBox migration
plan, why title and reason are split).

## Tracking Completed Work

`kb win add CONTEXT TITLE [BODY]` records a piece of completed work that was never tracked as a
pending Todo -- it was conceived, done, and finished in one sitting. A win IS a Todo (same
title/notes/context/effort/embedding shape as `kb todo add`, so it's reachable via `kb search`,
`context tree`, `journal`, `link` like any other Todo); the only difference is that it's
created already `status=DONE` instead of passing through `pending`/`in_progress` first, so it
never shows up in `todo pending`/`todo list`. This is distinct from completing an existing
Todo/Goal (`kb todo complete ID`): a win is for work that had no prior record at all, not the
resolution of one that did -- don't retroactively create a Todo just to complete it, and don't
use `kb win add` for something that was already tracked as pending. `kb win recent` (default:
last 7 calendar days including today, `--days 1` for just today) answers "what did we
accomplish today/this week?" -- any Todo completed in the window, not only ones added via
`kb win add`, since a Todo that really was pending first and got completed is equally "work
that got done recently."

## Searching Documents

"What does this page/PDF say about X", "search this doc for X", or "how similar are these two
texts" is `kb text extract` (pull clean paragraphs from a URL/PDF/HTML/text file/stdin) piped
into `kb text semsearch` (rank or compare those paragraphs by embedding) -- grouped under one
`kb text` parent since both are usable from any directory, not repo-local, and are two halves of
the same pipeline: `kb text extract URL | kb text semsearch rank "query"`. Run
`kb text extract --help` / `kb text semsearch --help` for the full usage.

## More

Run `kb <command> --help` before typing a command from memory -- flags and shapes above are
illustrative, not exhaustive. Run `kb -h` for full technical reference (what CONTEXT/--as-of
really do, the complete subcommand list). See also: kb instructions root and `kb i show
engineering` for the general CLI-ergonomics principle (applies across all projects, not just
kb) that governs how this file should read.
"""
