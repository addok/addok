import pytest

from addok.textutils.fr import _stemmize


@pytest.mark.parametrize('input,output', [
    ['cergy', 'serji'],
    ['andresy', 'andrezi'],
    ['conflans', 'konflan'],
    ['watel', 'vatel'],
    ['dunkerque', 'dunkerk'],
    ['robecq', 'robek'],
    ['wardrecques', 'vardrek'],
    ['cabourg', 'kabour'],
    ['audinghen', 'audingen'],
    ['sault', 'sau'],
    ['vaux', 'vau'],
    ['guyancourt', 'guiankour'],
])
def test_normalize(input, output):
    assert _stemmize(input) == output
