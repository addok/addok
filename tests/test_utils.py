import pytest

from kautchu.utils import (make_fuzzy, compare_ngrams, tokenize, normalize,
                           alphanumerize)


def test_make_fuzzy_should_extend_term():
    expected = set([
        'omt', 'mto', 'amot', 'maot', 'moat', 'mota', 'bmot', 'mbot', 'mobt',
        'motb', 'cmot', 'mcot', 'moct', 'motc', 'dmot', 'mdot', 'modt', 'motd',
        'emot', 'meot', 'moet', 'mote', 'fmot', 'mfot', 'moft', 'motf', 'gmot',
        'mgot', 'mogt', 'motg', 'hmot', 'mhot', 'moht', 'moth', 'imot', 'miot',
        'moit', 'moti', 'jmot', 'mjot', 'mojt', 'motj', 'kmot', 'mkot', 'mokt',
        'motk', 'lmot', 'mlot', 'molt', 'motl', 'mmot', 'mmot', 'momt', 'motm',
        'nmot', 'mnot', 'mont', 'motn', 'omot', 'moot', 'moot', 'moto', 'pmot',
        'mpot', 'mopt', 'motp', 'qmot', 'mqot', 'moqt', 'motq', 'rmot', 'mrot',
        'mort', 'motr', 'smot', 'msot', 'most', 'mots', 'tmot', 'mtot', 'mott',
        'mott', 'umot', 'muot', 'mout', 'motu', 'vmot', 'mvot', 'movt', 'motv',
        'wmot', 'mwot', 'mowt', 'motw', 'xmot', 'mxot', 'moxt', 'motx', 'ymot',
        'myot', 'moyt', 'moty', 'zmot', 'mzot', 'mozt', 'motz', 'aot', 'mat',
        'moa', 'bot', 'mbt', 'mob', 'cot', 'mct', 'moc', 'dot', 'mdt', 'mod',
        'eot', 'met', 'moe', 'fot', 'mft', 'mof', 'got', 'mgt', 'mog', 'hot',
        'mht', 'moh', 'iot', 'mit', 'moi', 'jot', 'mjt', 'moj', 'kot', 'mkt',
        'mok', 'lot', 'mlt', 'mol', 'mot', 'mmt', 'mom', 'not', 'mnt', 'mon',
        'oot', 'mot', 'moo', 'pot', 'mpt', 'mop', 'qot', 'mqt', 'moq', 'rot',
        'mrt', 'mor', 'sot', 'mst', 'mos', 'tot', 'mtt', 'mot', 'uot', 'mut',
        'mou', 'vot', 'mvt', 'mov', 'wot', 'mwt', 'mow', 'xot', 'mxt', 'mox',
        'yot', 'myt', 'moy', 'zot', 'mzt', 'moz',
    ])
    assert set(make_fuzzy('mot')) == expected


def test_compare_ngrams_should_return_one_for_same_string():
    assert compare_ngrams('Lille', 'Lille') == 1


def test_compare_ngrams_should_be_case_unsensitive():
    assert compare_ngrams('Lille', 'lille') == 1


def test_compare_ngrams_should_be_accent_unsensitive():
    assert compare_ngrams('Andrésy', 'andresy') == 1


@pytest.mark.parametrize('input,output', [
    ['one two three', ['one', 'two', 'three']],
    ["presqu'ile", ['presqu', 'ile']],
    ['22, rue', ['22', 'rue']],
])
def test_tokenize(input, output):
    assert tokenize(input) == output


@pytest.mark.parametrize('input,output', [
    ['ABCDEF', 'abcdef'],
    ['éêàù', 'eeau'],
    ['Étretat', 'etretat'],
])
def test_normalize(input, output):
    assert normalize(input) == output


@pytest.mark.parametrize('input,output', [
    ["rue d'Andrésy", 'rue d Andrésy'],
    ['   ', ' '],
])
def test_alphanumerize(input, output):
    assert alphanumerize(input) == output
