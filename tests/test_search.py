from addok.core import search
from addok.import_utils import index_document


def test_should_match_name(street):
    assert not search('Conflans')
    street['name'] = 'Conflans'
    index_document(street)
    results = search('Conflans')
    assert results
    result = results[0]
    assert result.name == 'Conflans'
    assert result.id == street['id']


def test_should_match_name_case_insensitive(street):
    assert not search('conflans')
    street['name'] = 'Conflans'
    index_document(street)
    assert search('conflans')


def test_should_match_name_with_accent(street):
    assert not search('andrésy')
    street['name'] = 'Andrésy'
    index_document(street)
    assert search('andrésy')


def test_should_match_name_without_accent(street):
    assert not search('andresy')
    street['name'] = 'Andrésy'
    index_document(street)
    assert search('andresy')


def test_should_give_priority_to_best_match(street, city):
    street['name'] = "rue d'Andrésy"
    index_document(street)
    city['name'] = 'Andrésy'
    index_document(city)
    results = search('andresy')
    assert results[0].id == city['id']


def test_should_give_priority_to_best_match2(street):
    street['name'] = "rue d'Andrésy"
    street['city'] = "Conflans"
    index_document(street)
    other = street.copy()
    other['id'] = "xxxx321456"
    other['name'] = "rue de Conflans"
    other['city'] = "Andrésy"
    index_document(other)
    results = search("rue andresy")
    assert len(results) == 2
    assert results[0].id == street['id']


def test_should_give_priority_to_best_match3(street):
    street['name'] = "rue de Lille"
    street['city'] = "Douai"
    index_document(street)
    other = street.copy()
    other['id'] = "xxxx321456"
    other['name'] = "rue de Douai"
    other['city'] = "Lille"
    index_document(other)
    results = search("rue de lille douai")
    assert len(results) == 2
    assert results[0].id == street['id']
    results = search("rue de douai lille")
    assert len(results) == 2
    assert results[0].id == other['id']


def test_should_be_fuzzy_of_1_by_default(city):
    city['name'] = "Andrésy"
    index_document(city)
    assert search('antresy')
    assert not search('antresu')


def test_fuzzy_should_work_with_inversion(city):
    city['name'] = "Andrésy"
    index_document(city)
    assert search('andreys')


def test_fuzzy_should_match_with_removal(city):
    city['name'] = "Andrésy"
    index_document(city)
    assert search('andressy')


def test_should_give_priority_to_housenumber_if_match(housenumber, street):
    housenumber['name'] = 'rue des Berges'
    housenumber['housenumber'] = 22
    street['name'] = 'rue des Berges'
    index_document(housenumber)
    index_document(street)
    results = search('22 rue des berges')
    assert len(results) == 1
    assert results[0].id == housenumber['id']


def test_should_do_autocomplete_on_last_term(street):
    street['name'] = 'rue de Wambrechies'
    street['city'] = 'Bondues'
    index_document(street)
    assert search('avenue wambre')
    assert not search('wambre avenue')


def test_synonyms_should_be_replaced(street, monkeypatch):
    monkeypatch.setattr('addok.textutils.default.SYNONYMS',
                        {'bd': 'boulevard'})
    street['name'] = 'boulevard des Fleurs'
    index_document(street)
    assert search('bd')
