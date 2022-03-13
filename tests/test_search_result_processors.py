import json

import pytest

from addok.batch import process_documents
from addok.core import search


@pytest.mark.parametrize(
    "input,expected",
    [
        ("rue du 8 mai troyes", False),
        ("8 rue du 8 mai troyes", "8"),
        ("3 rue du 8 mai troyes", "3"),
    ],
)
def test_match_housenumber(input, expected):
    doc = {
        "id": "xxxx",
        "_id": "yyyy",
        "type": "street",
        "name": "rue du 8 Mai",
        "city": "Troyes",
        "lat": "49.32545",
        "lon": "4.2565",
        "housenumbers": {
            "3": {"lat": "48.325451", "lon": "2.25651"},
            "3 bis": {"lat": "48.325451", "lon": "2.25651"},
            "8": {"lat": "48.325451", "lon": "2.25651"},
        },
    }
    process_documents(json.dumps(doc))
    result = search(input)[0]
    assert (result.type == "housenumber") == bool(expected)
    if expected:
        assert result.housenumber == expected
