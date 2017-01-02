import pytest

from addok.textutils.fr_FR import (_clean_query, _extract_address,
                                   _fold_ordinal, _glue_ordinal)


@pytest.mark.parametrize("input,expected", [
    ("2 allée Jules Guesde 31068 TOULOUSE CEDEX 7",
     "2 allée Jules Guesde 31068 TOULOUSE"),
    ("7, avenue Léon-Blum 31507 Toulouse Cedex 5",
     "7, avenue Léon-Blum 31507 Toulouse"),
    ("159, avenue Jacques-Douzans 31604 Muret Cedex",
     "159, avenue Jacques-Douzans 31604 Muret"),
    ("2 allée Jules Guesde BP 7015 31068 TOULOUSE",
     "2 allée Jules Guesde 31068 TOULOUSE"),
    ("BP 80111 159, avenue Jacques-Douzans 31604 Muret",
     "159, avenue Jacques-Douzans 31604 Muret"),
    ("12, place de l'Hôtel-de-Ville BP 46 02150 Sissonne",
     "12, place de l'Hôtel-de-Ville 02150 Sissonne"),
    ("6, rue Winston-Churchill CS 40055 60321 Compiègne",
     "6, rue Winston-Churchill 60321 Compiègne"),
    ("BP 80111 159, avenue Jacques-Douzans 31604 Muret Cedex",
     "159, avenue Jacques-Douzans 31604 Muret"),
    ("BP 20169 Cite administrative - 8e étage Rue Gustave-Delory 59017 Lille",
     "Cite administrative - Rue Gustave-Delory 59017 Lille"),
    ("12e étage Rue Gustave-Delory 59017 Lille",
     "Rue Gustave-Delory 59017 Lille"),
    ("12eme étage Rue Gustave-Delory 59017 Lille",
     "Rue Gustave-Delory 59017 Lille"),
    ("12ème étage Rue Gustave-Delory 59017 Lille",
     "Rue Gustave-Delory 59017 Lille"),
    ("Rue Louis des Etages",
     "Rue Louis des Etages"),
    ("route express",
     "route express"),
    ("air s/adour",
     "air sur adour"),
    ("air s/ l'adour",
     "air sur l'adour"),
    ("air-s/-l'adour",
     "air sur l'adour"),
    ("Saint Didier s/s Ecouves",
     "Saint Didier sous Ecouves"),
    ("La Chapelle-aux-Brocs",
     "La Chapelle-aux-Brocs"),
])
def test_clean_query(input, expected):
    assert _clean_query(input) == expected


@pytest.mark.parametrize("input,expected", [
    ('Immeuble Plein-Centre 60, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('75, rue Boucicaut 92260 Fontenay-aux-Roses',
     '75, rue Boucicaut 92260 Fontenay-aux-Roses'),
    ('rue Boucicaut 92260 Fontenay-aux-Roses',
     'rue Boucicaut 92260 Fontenay-aux-Roses'),
    ("Maison de l'emploi et de la formation 13, rue de la Tuilerie 70400 Héricourt",  # noqa
     "13, rue de la Tuilerie 70400 Héricourt"),
    # ("Parc d'activités Innopole 166, rue Pierre-et-Marie-Curie 31670 Labège",
    #  "166, rue Pierre-et-Marie-Curie 31670 Labège"),
    # ("32, allée Henri-Sellier Maison des solidarités 31400 Toulouse",
    #  "32, allée Henri-Sellier 31400 Toulouse"),
    # ("Centre d'Affaires la Boursidiere - BP 160 - Bâtiment Maine 4ème étage Le Plessis Robinson 92357 France",  # noqa
    #  "Le Plessis Robinson 92357 France"),
    # ("21 Rue Clef 34 Rue Daubenton",
    # "21 Rue Clef"),
    ("Tribunal d'instance de Guebwiller 1, place Saint-Léger 68504 Guebwiller",
     "1, place Saint-Léger 68504 Guebwiller"),
    ("Centre social 3 rue du Laurier 73000 CHAMBERY",
     "3 rue du Laurier 73000 CHAMBERY"),
    ("Maison de la Médiation 72 Chaussée de l'Hôtel de Ville 59650 VILLENEUVE D ASCQ",  # noqa
     "72 Chaussée de l'Hôtel de Ville 59650 VILLENEUVE D ASCQ"),
    ("2, Grande rue 62128 Écoust-Saint-Mein",
     "2, Grande rue 62128 Écoust-Saint-Mein"),
    ("Le Haut de la Rue du Bois 77122 Monthyon",
     "Le Haut de la Rue du Bois 77122 Monthyon"),
    ("Sous la Rue du Temple 62800 Liévin",
     "Sous la Rue du Temple 62800 Liévin"),
    # Two spaces after housenumber.
    ("resid goelands 28  impasse des petrels 76460 Saint-valery-en-caux",
     "28  impasse des petrels 76460 Saint-valery-en-caux"),
    # Two spaces after bis.
    ("resid goelands 28  bis impasse des petrels 76460 Saint-valery-en-caux",
     "28  bis impasse des petrels 76460 Saint-valery-en-caux"),
    # No spaces after bis.
    ("resid goelands 28bis impasse des petrels 76460 Saint-valery-en-caux",
     "28bis impasse des petrels 76460 Saint-valery-en-caux"),
    ("Non matching pattern",
     "Non matching pattern"),
])
def test_extract_address(input, expected):
    assert _extract_address(input) == expected


@pytest.mark.parametrize("input,expected", [
    ('60, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('60 avenue du Centre 78180 Montigny-le-Bretonneux',
     '60 avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('60 bis, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60bis, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('6 ter, avenue du Centre 78180 Montigny-le-Bretonneux',
     '6ter, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('600 quater, avenue du Centre 78180 Montigny-le-Bretonneux',
     '600quater, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('600 quinquies, avenue du Centre 78180 Montigny-le-Bretonneux',
     '600quinquies, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('60 b, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60b, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('60b, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60b, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('60 s, avenue du Centre 78180 Montigny-le-Bretonneux',
     '60s, avenue du Centre 78180 Montigny-le-Bretonneux'),
    ('place des Terreaux Lyon',
     'place des Terreaux Lyon'),
    ('241 r de fayet',
     '241 r de fayet'),
    ('241 r rue de fayet',
     '241r rue de fayet'),
])
def test_glue_ordinal(input, expected):
    assert _glue_ordinal(input) == expected


@pytest.mark.parametrize("input,expected", [
    ('60bis', '60b'),
    ('60BIS', '60b'),
    ('60ter', '60t'),
    ('4terre', '4terre'),
    ('60quater', '60q'),
    ('60 bis', '60 bis'),
    ('rue du bis', 'rue du bis'),
])
def test_fold_ordinal(input, expected):
    assert _fold_ordinal(input) == expected
