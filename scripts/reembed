#!/usr/bin/env python3
"""Recompute embeddings for all notes. Run after switching embedding models."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from embed import model_name
from models import Note, sess

notes = sess.scalars(select(Note)).all()
if not notes:
    print("No notes to reembed.")
    sys.exit(0)

print(f"Reembedding {len(notes)} notes with model '{model_name()}'...")
for i, note in enumerate(notes, 1):
    note.reembed()
    print(f"  [{i}/{len(notes)}] {note.title!r}")

sess.commit()
print("Done.")
