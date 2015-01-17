import pytest

from addok.textutils.default import (make_fuzzy, compare_ngrams, normalize,
                                     alphanumerize, synonymize, tokenize,
                                     compute_edge_ngrams, string_contain)


@pytest.mark.parametrize('input,output', [
    ['one two three', ['one', 'two', 'three']],
    ["presqu'ile", ['presqu', 'ile']],
    ['22, rue', ['22', 'rue']],
])
def test_tokenize(input, output):
    assert tokenize(input) == output


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
        'mok', 'lot', 'mlt', 'mol', 'mmt', 'mom', 'not', 'mnt', 'mon',
        'oot', 'moo', 'pot', 'mpt', 'mop', 'qot', 'mqt', 'moq', 'rot',
        'mrt', 'mor', 'sot', 'mst', 'mos', 'tot', 'mtt', 'uot', 'mut',
        'mou', 'vot', 'mvt', 'mov', 'wot', 'mwt', 'mow', 'xot', 'mxt', 'mox',
        'yot', 'myt', 'moy', 'zot', 'mzt', 'moz',
    ])
    assert set(make_fuzzy('mot')) == expected


def test_make_fuzzy_should_remove_letter_if_world_is_long():
    assert 'mt' not in make_fuzzy('mot')
    assert 'rain' in make_fuzzy('train')
    assert 'tain' in make_fuzzy('train')
    assert 'trin' in make_fuzzy('train')
    assert 'tran' in make_fuzzy('train')
    assert 'trai' in make_fuzzy('train')


def test_compare_ngrams_should_return_one_for_same_string():
    assert compare_ngrams('Lille', 'Lille') == 1


def test_compare_ngrams_should_be_case_unsensitive():
    assert compare_ngrams('Lille', 'lille') == 1


def test_compare_ngrams_should_be_accent_unsensitive():
    assert compare_ngrams('Andrésy', 'andresy') == 1


@pytest.mark.parametrize('input,output', [
    ['ABCDEF', 'abcdef'],
    ['éêàù', 'eeau'],
    ['Étretat', 'etretat'],
    ['Erispœ', 'erispoe'],
])
def test_normalize(input, output):
    assert normalize(input) == output


@pytest.mark.parametrize('input,output', [
    ["rue d'Andrésy", 'rue d Andrésy'],
    ['   ', ' '],
])
def test_alphanumerize(input, output):
    assert alphanumerize(input) == output


@pytest.mark.parametrize('input,output', [
    ['bd', 'boulevard'],
    ['13e', 'treizieme'],
])
def test_synonymize(input, output, monkeypatch):
    # Make sure we control synonyms.
    SYNONYMS = {'bd': 'boulevard', '13e': 'treizieme'}
    monkeypatch.setattr('addok.textutils.default.SYNONYMS', SYNONYMS)
    assert synonymize(input) == output


def test_compute_edge_ngrams():
    assert compute_edge_ngrams('vanbrechi') == [
        'van', 'vanb', 'vanbr', 'vanbre', 'vanbrec', 'vanbrech'
    ]


@pytest.mark.parametrize('candidate,target', [
    ['22 rue vicq', "22 Rue Vicq d'Azir 75010 Paris"],
])
def test_string_contain(candidate, target):
    assert string_contain(candidate, target)
