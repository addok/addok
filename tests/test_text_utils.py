import pytest

from addok.helpers.text import (_normalize, _synonymize, _tokenize,
                                alphanumerize, ascii, compare_ngrams,
                                compute_edge_ngrams, contains, equals,
                                make_fuzzy, startswith, Token)


@pytest.mark.parametrize('input,output', [
    ['one two three', ['one', 'two', 'three']],
    ["presqu'ile", ['presqu', 'ile']],
    ['22, rue', ['22', 'rue']],
])
def test_tokenize(input, output):
    assert _tokenize(input) == output


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


@pytest.mark.parametrize('left,right,score', [
    ['Lille', 'Lille', 1],
    ['Lille', 'lille', 1],
    ['Andrésy', 'andresy', 1],
    ['Y', 'y', 1],
    ['Ay', 'ay', 1],
])
def test_compare_ngrams(left, right, score):
    assert compare_ngrams(left, right) == score


@pytest.mark.parametrize('input,output', [
    ['ABCDEF', 'abcdef'],
    ['éêàù', 'eeau'],
    ['Étretat', 'etretat'],
    ['Erispœ', 'erispoe'],
])
def test_normalize(input, output):
    assert _normalize(Token(input)) == output


@pytest.mark.parametrize('input,output', [
    ["rue d'Andrésy", 'rue d Andrésy'],
    ['   ', ' '],
])
def test_alphanumerize(input, output):
    assert alphanumerize(Token(input)) == output


@pytest.mark.parametrize('input,output', [
    ['bd', 'boulevard'],
    ['13e', 'treizieme'],
])
def test_synonymize(input, output, monkeypatch):
    # Make sure we control synonyms.
    SYNONYMS = {'bd': 'boulevard', '13e': 'treizieme'}
    monkeypatch.setattr('addok.helpers.text.SYNONYMS', SYNONYMS)
    assert _synonymize(Token(input)) == output


def test_compute_edge_ngrams():
    assert compute_edge_ngrams('vanbrechi') == [
        'van', 'vanb', 'vanbr', 'vanbre', 'vanbrec', 'vanbrech'
    ]


def test_compute_edge_ngrams_honor_min_edge_ngrams_setting(config):
    config.MIN_EDGE_NGRAMS = 1
    assert compute_edge_ngrams('abcd') == ['a', 'ab', 'abc']


def test_compute_edge_ngrams_honor_max_edge_ngrams_setting(config):
    config.MAX_EDGE_NGRAMS = 5
    assert compute_edge_ngrams('abcdefghijklmn') == ['abc', 'abcd', 'abcde']


@pytest.mark.parametrize('candidate,target', [
    ['22 rue vicq', "22 Rue Vicq d'Azir 75010 Paris"],
    ['rue vicq', "22 Rue Vicq d'Azir 75010 Paris"],
])
def test_contains(candidate, target):
    assert contains(candidate, target)


@pytest.mark.parametrize('candidate,target', [
    ['22 rue vicq', "22 Rue Vicq d'Azir 75010 Paris"],
    ['etang des rivieres', "Étang des Rivières 42330 Saint-Galmier"],
])
def test_startswith(candidate, target):
    assert startswith(candidate, target)


@pytest.mark.parametrize('candidate,target', [
    ["22 rue vicq d azir 75010 paris", "22 Rue Vicq d'Azir 75010 Paris"],
    ['etang des rivieres', "Étang des Rivières"],
    ['Saint galmier', "Saint-Galmier"],
])
def test_equals(candidate, target):
    assert equals(candidate, target)


def test_ascii_should_behave_like_a_string():
    s = ascii('mystring')
    assert str(s) == 'mystring'


def test_ascii_should_clean_string():
    s = ascii(u'Aystringé')
    assert s == 'aystringe'


def test_ascii_should_cache_cleaned_string(monkeypatch):
    s = ascii('mystring')
    assert s._cache

    def do_not_call_me(x):
        assert False

    monkeypatch.setattr('addok.helpers.text.alphanumerize',
                        do_not_call_me)

    ascii(s)  # Should not call alphanumerize.
