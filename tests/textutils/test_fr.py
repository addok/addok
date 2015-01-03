import pytest

from addok.textutils.fr import _stemmize, _clean_query, _extract_address


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
    ['abasset', 'abaset'],
    ['agenest', 'ajenest'],
    ['allmendhurst', 'almendurst'],
    ['ableh', 'abl'],
    ['abilhous', 'abilou'],
    ['aberystwyth', 'aberistvit'],
    ['amfreville', 'anfrevil'],
    ['rimfort', 'rinfor'],
    ['pietricaggio', 'pietrikagio'],
    ['abatesco', 'abatesko'],
    ['albiosc', 'albiosk'],
    ['desc', 'desk'],
    ['bricquebec', 'brikebek'],
    ['locmariaquer', 'lokmariaker'],
    ['ancetres', 'ansetr'],
    ['vicdessos', 'vikdeso'],
    ['acacias', 'akasia'],
    ['placis', 'plasi'],
    ['courcome', 'kourkom'],
    ['hazebrouck', 'azebrouk'],
    ['blotzheim', 'blotzeim'],
    ['plouhinec', 'plouinek'],
    ['hirschland', 'irchlan'],
    ['schlierbach', 'chlierbak'],
    ['aebtissinboesch', 'aebtisinbech'],
    ['boescherbach', 'becherbak'],
    ['affelderwoert', 'afelderver'],
    ['boeuff', 'beuf'],
    ['humeroeuille', 'umereuil'],
    ['aigueboeuf', 'aigebeuf'],
    ['boeshoernel', 'bechernel'],
])
def test_normalize(input, output):
    assert _stemmize(input) == output


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
    ("Maison de l'emploi et de la formation 13, rue de la Tuilerie 70400 Héricourt",
     "13, rue de la Tuilerie 70400 Héricourt"),
    # ("Parc d'activités Innopole 166, rue Pierre-et-Marie-Curie 31670 Labège",
    #  "166, rue Pierre-et-Marie-Curie 31670 Labège"),
    # ("32, allée Henri-Sellier Maison des solidarités 31400 Toulouse",
    #  "32, allée Henri-Sellier 31400 Toulouse"),
    # ("Centre d'Affaires la Boursidiere - BP 160 - Bâtiment Maine 4ème étage Le Plessis Robinson 92357 France",
    #  "Le Plessis Robinson 92357 France"),
    ("Tribunal d'instance de Guebwiller 1, place Saint-Léger 68504 Guebwiller",
     "1, place Saint-Léger 68504 Guebwiller"),
    ("Centre social 3 rue du Laurier 73000 CHAMBERY",
     "3 rue du Laurier 73000 CHAMBERY"),
    ("Non matching pattern",
     "Non matching pattern"),
])
def test_match_address(input, expected):
    assert _extract_address(input) == expected
