from kautchu.core import search
from kautchu.import_utils import index_document


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
