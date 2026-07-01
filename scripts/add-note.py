#!/usr/bin/env python3
"""Add a note. Usage: add-note COLLECTION TITLE BODY [--tags tag1,tag2]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import KBClient
from models import Collection

parser = argparse.ArgumentParser(description="Add a knowledge base note")
parser.add_argument("collection", choices=[c.value for c in Collection if c != Collection.ALL])
parser.add_argument("title")
parser.add_argument("body")
parser.add_argument("--tags", default=None, help="Comma-separated tags")
args = parser.parse_args()

client = KBClient()
result = client.note_create(title=args.title, body=args.body, collection=args.collection, tags=args.tags)
print(f"Added: {result}")
