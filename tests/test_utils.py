import pytest

from addok.utils import import_by_path
from addok.textutils.default.pipeline import tokenize


@pytest.mark.parametrize("input,expected", [
    ('addok.textutils.default.pipeline.tokenize', tokenize),
    (tokenize, tokenize),
])
def test_import_by_path(input, expected):
    assert import_by_path(input) == expected
