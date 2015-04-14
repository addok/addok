"""Import data from the BANO project."""
import json

from .utils import batch


def row_to_doc(row):
    try:
        return json.loads(row)
    except ValueError:
        return None


def process_file(filepath):
    with open(filepath) as f:
        batch(map(row_to_doc, f))


def process_stdin(stdin):
    print('Import from stdin')
    batch(map(row_to_doc, stdin))
