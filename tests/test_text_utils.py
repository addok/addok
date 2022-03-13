import pytest
from addok.fuzzy import make_fuzzy
from addok.helpers.text import (
    Token,
    _normalize,
    _tokenize,
    alphanumerize,
    ascii,
    compare_str,
    compute_edge_ngrams,
    contains,
    equals,
    ngrams,
    startswith,
    synonymize,
)


@pytest.mark.parametrize(
    "input,output",
    [
        ["one two three", ["one", "two", "three"]],
        ["presqu'ile", ["presqu", "ile"]],
        ["22, rue", ["22", "rue"]],
    ],
)
def test_tokenize(input, output):
    assert _tokenize(input) == output


def test_make_fuzzy_should_extend_term(config):
    config.FUZZY_KEY_MAP = None
    expected = set(
        [
            "omt",
            "mto",
            "amot",
            "maot",
            "moat",
            "mota",
            "bmot",
            "mbot",
            "mobt",
            "motb",
            "cmot",
            "mcot",
            "moct",
            "motc",
            "dmot",
            "mdot",
            "modt",
            "motd",
            "emot",
            "meot",
            "moet",
            "mote",
            "fmot",
            "mfot",
            "moft",
            "motf",
            "gmot",
            "mgot",
            "mogt",
            "motg",
            "hmot",
            "mhot",
            "moht",
            "moth",
            "imot",
            "miot",
            "moit",
            "moti",
            "jmot",
            "mjot",
            "mojt",
            "motj",
            "kmot",
            "mkot",
            "mokt",
            "motk",
            "lmot",
            "mlot",
            "molt",
            "motl",
            "mmot",
            "mmot",
            "momt",
            "motm",
            "nmot",
            "mnot",
            "mont",
            "motn",
            "omot",
            "moot",
            "moot",
            "moto",
            "pmot",
            "mpot",
            "mopt",
            "motp",
            "qmot",
            "mqot",
            "moqt",
            "motq",
            "rmot",
            "mrot",
            "mort",
            "motr",
            "smot",
            "msot",
            "most",
            "mots",
            "tmot",
            "mtot",
            "mott",
            "mott",
            "umot",
            "muot",
            "mout",
            "motu",
            "vmot",
            "mvot",
            "movt",
            "motv",
            "wmot",
            "mwot",
            "mowt",
            "motw",
            "xmot",
            "mxot",
            "moxt",
            "motx",
            "ymot",
            "myot",
            "moyt",
            "moty",
            "zmot",
            "mzot",
            "mozt",
            "motz",
            "aot",
            "mat",
            "moa",
            "bot",
            "mbt",
            "mob",
            "cot",
            "mct",
            "moc",
            "dot",
            "mdt",
            "mod",
            "eot",
            "met",
            "moe",
            "fot",
            "mft",
            "mof",
            "got",
            "mgt",
            "mog",
            "hot",
            "mht",
            "moh",
            "iot",
            "mit",
            "moi",
            "jot",
            "mjt",
            "moj",
            "kot",
            "mkt",
            "mok",
            "lot",
            "mlt",
            "mol",
            "mmt",
            "mom",
            "not",
            "mnt",
            "mon",
            "oot",
            "moo",
            "pot",
            "mpt",
            "mop",
            "qot",
            "mqt",
            "moq",
            "rot",
            "mrt",
            "mor",
            "sot",
            "mst",
            "mos",
            "tot",
            "mtt",
            "uot",
            "mut",
            "mou",
            "vot",
            "mvt",
            "mov",
            "wot",
            "mwt",
            "mow",
            "xot",
            "mxt",
            "mox",
            "yot",
            "myt",
            "moy",
            "zot",
            "mzt",
            "moz",
        ]
    )
    assert set(make_fuzzy("mot")) == expected


def test_make_fuzzy_with_key_map_should_extend_term():
    expected = set(
        [
            "omt",
            "mto",
            "lot",
            "pot",
            "uot",
            "mit",
            "mat",
            "mkt",
            "mlt",
            "mpt",
            "mor",
            "mof",
            "mog",
            "moy",
            "amot",
            "maot",
            "moat",
            "mota",
            "bmot",
            "mbot",
            "mobt",
            "motb",
            "cmot",
            "mcot",
            "moct",
            "motc",
            "dmot",
            "mdot",
            "modt",
            "motd",
            "emot",
            "meot",
            "moet",
            "mote",
            "fmot",
            "mfot",
            "moft",
            "motf",
            "gmot",
            "mgot",
            "mogt",
            "motg",
            "hmot",
            "mhot",
            "moht",
            "moth",
            "imot",
            "miot",
            "moit",
            "moti",
            "jmot",
            "mjot",
            "mojt",
            "motj",
            "kmot",
            "mkot",
            "mokt",
            "motk",
            "lmot",
            "mlot",
            "molt",
            "motl",
            "mmot",
            "momt",
            "motm",
            "nmot",
            "mnot",
            "mont",
            "motn",
            "omot",
            "moot",
            "moto",
            "pmot",
            "mpot",
            "mopt",
            "motp",
            "qmot",
            "mqot",
            "moqt",
            "motq",
            "rmot",
            "mrot",
            "mort",
            "motr",
            "smot",
            "msot",
            "most",
            "mots",
            "tmot",
            "mtot",
            "mott",
            "umot",
            "muot",
            "mout",
            "motu",
            "vmot",
            "mvot",
            "movt",
            "motv",
            "wmot",
            "mwot",
            "mowt",
            "motw",
            "xmot",
            "mxot",
            "moxt",
            "motx",
            "ymot",
            "myot",
            "moyt",
            "moty",
            "zmot",
            "mzot",
            "mozt",
            "motz",
        ]
    )
    assert set(make_fuzzy("mot")) == expected


def test_make_fuzzy_should_remove_letter_if_world_is_long():
    assert "mt" not in make_fuzzy("mot")
    assert "rain" in make_fuzzy("train")
    assert "tain" in make_fuzzy("train")
    assert "trin" in make_fuzzy("train")
    assert "tran" in make_fuzzy("train")
    assert "trai" in make_fuzzy("train")


@pytest.mark.parametrize(
    "left,right,score",
    [
        ["Lille", "Lille", 1],
        ["Lille", "lille", 1],
        ["Andrésy", "andresy", 1],
        ["Y", "y", 1],
        ["Ay", "ay", 1],
    ],
)
def test_compare_str(left, right, score):
    assert compare_str(left, right) == score


@pytest.mark.parametrize(
    "best,other,query",
    [
        [
            "avenue de paris 94123 saint mande",
            "avenue de saint mande 75012 paris",
            "avenue de paris saint mande",
        ],
        [
            "1 place du trocadero et du 11 novembre 75016 paris",
            "square du trocadero 75016 paris",
            "place du trocadero paris",
        ],
    ],
)
def test_compare_strs(best, other, query):
    assert compare_str(best, query) > compare_str(other, query)


@pytest.mark.parametrize(
    "input,n,output",
    [
        ["Lille", 2, {" L", "Li", "il", "ll", "le", "e "}],
        ["Lille", 3, {" Li", "Lil", "ill", "lle", "le "}],
        ["L", 3, {" L "}],
    ],
)
def test_ngrams(input, n, output):
    assert ngrams(input, n) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ["ABCDEF", "abcdef"],
        ["éêàù", "eeau"],
        ["Étretat", "etretat"],
        ["Erispœ", "erispoe"],
    ],
)
def test_normalize(input, output):
    assert _normalize(Token(input)) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ["rue d'Andrésy", "rue d Andrésy"],
        ["a   ", "a"],
        ["(défibrillateur)", "défibrillateur"],
        ["machin (défibrillateur)", "machin défibrillateur"],
    ],
)
def test_alphanumerize(input, output):
    assert alphanumerize(Token(input)) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ["bd", ["boulevard"]],
        ["13e", ["treizieme"]],
        ["18e", ["dix", "huitieme"]],
    ],
)
def test_synonymize(input, output, config):
    # Make sure we control synonyms.
    config.SYNONYMS = {"bd": "boulevard", "13e": "treizieme", "18e": "dix huitieme"}
    assert list(synonymize([Token(input)])) == output


def test_synonyms_file_is_loaded(config):
    # See synonyms.txt
    assert config.SYNONYMS == {
        "cba": "abc",
        "xzy": "xyz",
        "zyx": "xyz",
    }


def test_compute_edge_ngrams():
    assert compute_edge_ngrams("vanbrechi") == [
        "van",
        "vanb",
        "vanbr",
        "vanbre",
        "vanbrec",
        "vanbrech",
    ]


def test_compute_edge_ngrams_honor_min_edge_ngrams_setting(config):
    config.MIN_EDGE_NGRAMS = 1
    assert compute_edge_ngrams("abcd") == ["a", "ab", "abc"]


def test_compute_edge_ngrams_honor_max_edge_ngrams_setting(config):
    config.MAX_EDGE_NGRAMS = 5
    assert compute_edge_ngrams("abcdefghijklmn") == ["abc", "abcd", "abcde"]


@pytest.mark.parametrize(
    "candidate,target",
    [
        ["22 rue vicq", "22 Rue Vicq d'Azir 75010 Paris"],
        ["rue vicq", "22 Rue Vicq d'Azir 75010 Paris"],
    ],
)
def test_contains(candidate, target):
    assert contains(candidate, target)


@pytest.mark.parametrize(
    "candidate,target",
    [
        ["22 rue vicq", "22 Rue Vicq d'Azir 75010 Paris"],
        ["etang des rivieres", "Étang des Rivières 42330 Saint-Galmier"],
    ],
)
def test_startswith(candidate, target):
    assert startswith(candidate, target)


@pytest.mark.parametrize(
    "candidate,target",
    [
        ["22 rue vicq d azir 75010 paris", "22 Rue Vicq d'Azir 75010 Paris"],
        ["etang des rivieres", "Étang des Rivières"],
        ["Saint galmier", "Saint-Galmier"],
    ],
)
def test_equals(candidate, target):
    assert equals(candidate, target)


def test_ascii_should_behave_like_a_string():
    s = ascii("mystring")
    assert str(s) == "mystring"


def test_ascii_should_clean_string():
    s = ascii("Aystringé")
    assert s == "aystringe"


def test_ascii_should_cache_cleaned_string(monkeypatch):
    s = ascii("mystring")
    assert s._cache

    def do_not_call_me(x):
        assert False


def test_ngrams_should_cache():
    ngrams("test")
    assert ngrams.cache_info() is not None
