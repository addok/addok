import pytest

from addok.http import app as myapp


def pytest_configure():
    from addok.config import config as addok_config
    addok_config.SYNONYMS_PATH = 'tests/synonyms.txt'


@pytest.fixture
def app():
    return myapp
