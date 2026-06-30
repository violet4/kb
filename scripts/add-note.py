#!/usr/bin/env python3
"""Add a note. Usage: add-note COLLECTION TITLE BODY [--tags tag1,tag2]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Collection, Note, sess

parser = argparse.ArgumentParser(description="Add a knowledge base note")
parser.add_argument("collection", choices=[c.value for c in Collection if c != Collection.ALL])
parser.add_argument("title")
parser.add_argument("body")
parser.add_argument("--tags", default=None, help="Comma-separated tags")
args = parser.parse_args()

collection = Collection(args.collection)
note = Note.create(args.title, args.body, collection, tags=args.tags)
sess.commit()
print(f"Added: {note}")
