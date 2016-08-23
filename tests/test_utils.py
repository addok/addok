import pytest
from addok.helpers import import_by_path
from addok.helpers.text import tokenize


@pytest.mark.parametrize("input,expected", [
    ('addok.helpers.text.tokenize', tokenize),
    (tokenize, tokenize),
])
def test_import_by_path(input, expected):
    assert import_by_path(input) == expected
