import pytest

from addok.helpers import import_by_path, load_csv_file
from addok.helpers.text import tokenize


@pytest.mark.parametrize(
    "input,expected",
    [
        ("addok.helpers.text.tokenize", tokenize),
        (tokenize, tokenize),
    ],
)
def test_import_by_path(input, expected):
    assert import_by_path(input) == expected


def test_import_csv_file():
    assert list(load_csv_file("tests/test.csv")) == [
        {"name": "foo", "city": "bar", "somethingelse": "baz"},
        {
            "name": "another",
            "city": "line",
            "somethingelse": "complete",
        },
    ]
