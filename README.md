# kb — Personal Knowledge Base

A persistent, queryable store for notes, goals, people, references, and working memory. Vector search makes notes discoverable by meaning, not exact wording.

## What's tracked

| Entity | What it holds |
|---|---|
| **Note** | Atomic knowledge notes, searchable by meaning via vector embeddings |
| **Person** | People: closeness, last contacted, reach-out cadence |
| **Goal** | Life goals with status |
| **Todo** | Tasks linked to goals |
| **Wishlist** | Things to acquire: price, importance, urgency, effort, clarity, priority |
| **Reference** | URLs and resources with tags |
| **WorkingMemory** | Transient context: current task state, active threads |
| **Context** | Scoping label (personal, work, etc.) |

## Note collections

Notes are partitioned by collection — searches never cross collections accidentally.

`engineering` · `personal` · `gorgon` · `work`

## Scripts

```bash
uv run scripts/summary                          # daily overview
uv run scripts/notes add COLLECTION TITLE BODY [--tags x,y]
uv run scripts/notes search COLLECTION QUERY
uv run scripts/notes update (--id ID | --find TITLE) [--title T] [--body B] [--tags t1,t2]
uv run scripts/notes reembed                     # recompute embeddings after model upgrade
uv run scripts/model/download                    # fetch/update embedding model from HuggingFace; run once on setup or when upgrading models — after this, all embedding runs offline/local
uv run scripts/wishlist/add                      # interactively add a wishlist item
uv run scripts/todo show ID [ID ...]
uv run scripts/todo complete ID [ID ...]
uv run scripts/dev/gen-api [ClassName ...]       # print the API surface, live from models.py
```

## Server

```bash
scripts/service/status
scripts/service/restart
scripts/service/is-active
```
