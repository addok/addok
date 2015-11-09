import json

from addok.utils import yielder


@yielder
def to_json(row):
    try:
        return json.loads(row)
    except ValueError:
        return None
