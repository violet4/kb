#!/usr/bin/env python3
"""Update a note by id or title. Usage: update-note.py (--id ID | --find TITLE) [--title T] [--body B] [--tags t1,t2]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Note, sess

parser = argparse.ArgumentParser(description="Update a knowledge base note")
lookup = parser.add_mutually_exclusive_group(required=True)
lookup.add_argument("--id", type=int, help="Note id")
lookup.add_argument("--find", metavar="TITLE", help="Find note by exact title")
parser.add_argument("--title", help="New title")
parser.add_argument("--body", help="New body")
parser.add_argument("--tags", help="New tags (comma-separated)")
args = parser.parse_args()

note = Note.get(args.id) if args.id else Note.find(args.find)
if note is None:
    print(f"Note not found.", file=sys.stderr)
    sys.exit(1)

note.update(title=args.title, body=args.body, tags=args.tags)
sess.commit()
print(f"Updated: {note}")
