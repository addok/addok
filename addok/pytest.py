"""
Exposes a pytest plugin so addok plugins do not need to recode all the test
setup logic.
"""

import json
import os
from pathlib import Path
import uuid

import pytest

# Do not import files from the top of the module, otherwise they will
# not be taken into account by the coverage.


def pytest_configure():
    from addok.config import config as addok_config

    addok_config.__class__.TESTING = True
    # Force test config.
    from addok import config as config_module

    os.environ["ADDOK_CONFIG_MODULE"] = str(
        Path(config_module.__file__).parent / "test.py"
    )
    import logging

    logging.basicConfig(level=logging.DEBUG)
    addok_config.REDIS["indexes"]["db"] = 14
    addok_config.REDIS["documents"]["db"] = 15
    addok_config.load()


def pytest_runtest_setup(item):
    from addok import db, ds
    from addok.config import config as addok_config

    assert db.DB.connection_pool.connection_kwargs["db"] == 14
    if addok_config.DOCUMENT_STORE == ds.RedisStore:
        assert ds._DB.connection_pool.connection_kwargs["db"] == 15


def pytest_runtest_teardown(item, nextitem):
    from addok import db, ds
    from addok.config import config as addok_config

    assert db.DB.connection_pool.connection_kwargs["db"] == 14
    db.DB.flushdb()
    if addok_config.DOCUMENT_STORE == ds.RedisStore:
        assert ds._DB.connection_pool.connection_kwargs["db"] == 15
        ds._DB.flushdb()


def pytest_addoption(parser):
    group = parser.getgroup("general")
    group._addoption(
        "--shell",
        action="store_true",
        dest="addokshell",
        default=False,
        help="start addok interactive shell on error.",
    )


def pytest_exception_interact(node, call, report):
    if node.config.getvalue("addokshell"):
        from addok.shell import invoke

        invoke()


class DummyDoc(dict):
    def __init__(self, *args, **kwargs):
        skip_index = kwargs.pop("skip_index", False)
        super().__init__(*args, **kwargs)
        if not skip_index:
            self.index()

    def update(self, **kwargs):
        super().update(kwargs)
        self.index()

    def index(self):
        from addok.batch import process_documents

        process_documents(json.dumps(self.copy()))


@pytest.fixture
def factory(request):
    from addok import db

    def _(**kwargs):
        default = {
            "id": uuid.uuid4().hex,
            "_id": db.DB.next_id(),
            "type": "street",
            "name": "ellington",
            "importance": 0.0,
            "lat": "48.3254",
            "lon": "2.256",
        }
        default.update(kwargs)
        doc = DummyDoc(**default)
        return doc

    return _


@pytest.fixture
def street(factory):
    return factory()


@pytest.fixture
def city(factory):
    return factory(type="city")


@pytest.fixture
def housenumber(factory):
    return factory(housenumbers={"11": {"lat": "48.3254", "lon": "2.256"}})


@pytest.fixture
def app():
    # Do not import before redis config has been
    # patched.
    from addok.http.wsgi import application

    return application


@pytest.fixture
def client(app):
    """Provide a Falcon test client accepting dict query strings."""
    from falcon import testing
    from urllib.parse import urlencode

    class _Client(testing.TestClient):
        def get(self, path, **kwargs):
            qs = kwargs.get("query_string")
            if isinstance(qs, dict):
                # simulate the behavior of pytest-falcon which accepted dicts
                kwargs["query_string"] = urlencode(qs, doseq=True)
            return super().get(path, **kwargs)

    return _Client(app)


class MonkeyPatchWrapper(object):
    def __init__(self, monkeypatch, wrapped_object):
        super().__setattr__("monkeypatch", monkeypatch)
        super().__setattr__("wrapped_object", wrapped_object)

    def __getattr__(self, attr):
        return getattr(self.wrapped_object, attr)

    def __setattr__(self, attr, value):
        self.monkeypatch.setattr(self.wrapped_object, attr, value, raising=False)

    def __delattr__(self, attr):
        self.monkeypatch.delattr(self.wrapped_object, attr)


@pytest.fixture()
def config(request, monkeypatch):
    from addok.config import config as addok_config

    return MonkeyPatchWrapper(monkeypatch, addok_config)
