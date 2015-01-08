import uuid
import pytest


def pytest_configure(config):
    from addok.config import DB_SETTINGS
    DB_SETTINGS['db'] = 15
    import logging
    logging.basicConfig(level=logging.DEBUG)


def pytest_runtest_teardown(item, nextitem):
    from addok.core import DB
    assert DB.connection_pool.connection_kwargs['db'] == 15
    DB.flushdb()


@pytest.fixture
def factory(request):
    def _(**kwargs):
        doc = {
            'id': uuid.uuid4().hex,
            'type': 'street',
            'name': 'ellington',
            'importance': 0.0,
            'lat': '48.3254',
            'lon': '2.256'
        }
        doc.update(kwargs)
        return doc
    return _


@pytest.fixture
def street(factory):
    return factory()


@pytest.fixture
def city(factory):
    return factory(type='city')


@pytest.fixture
def housenumber(factory):
    return factory(housenumbers={'11': {'lat': '48.3254', 'lon': '2.256'}})
