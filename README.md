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
uv run scripts/summary.py              # daily overview
uv run scripts/add-note.py COLLECTION TITLE BODY [--tags x,y]
uv run scripts/download-model.py       # fetch/update embedding model (only HF network call)
uv run scripts/reembed.py              # recompute embeddings after model upgrade
```

## Server

```bash
systemctl --user status kb
journalctl --user -u kb -f
```
