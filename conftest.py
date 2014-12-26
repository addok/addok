import uuid
import pytest


def pytest_configure(config):
    from kautchu.config import DB_SETTINGS
    DB_SETTINGS['db'] = 15


def pytest_runtest_teardown(item, nextitem):
    from kautchu.core import DB
    assert DB.connection_pool.connection_kwargs['db'] == 15
    DB.flushdb()


@pytest.fixture
def doc(request):
    return {
        'id': uuid.uuid4().hex,
        'importance': 0.0
    }.copy()


@pytest.fixture
def street(doc):
    doc['type'] = 'street'
    return doc


@pytest.fixture
def city(doc):
    doc['type'] = 'city'
    return doc


@pytest.fixture
def housenumber(doc):
    doc['type'] = 'housenumber'
    doc['housenumber'] = 11
    return doc
