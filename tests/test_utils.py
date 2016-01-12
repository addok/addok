import pytest

from addok.utils import import_by_path
from addok.text_utils import tokenize


@pytest.mark.parametrize("input,expected", [
    ('addok.text_utils.tokenize', tokenize),
    (tokenize, tokenize),
])
def test_import_by_path(input, expected):
    assert import_by_path(input) == expected
