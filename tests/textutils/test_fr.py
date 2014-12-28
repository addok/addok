import pytest

from addok.textutils.fr import _stemmize


@pytest.mark.parametrize('input,output', [
    ['cergy', 'serji'],
    ['andresy', 'andrezi'],
    ['conflans', 'konflan'],
    ['watel', 'vatel'],
])
def test_normalize(input, output):
    assert _stemmize(input) == output
