import json

from addok.batch import process_documents, reset
from addok.core import search
from addok.db import DB


def test_process_should_index_by_default(factory):
    doc = factory(skip_index=True, name="Melicocq")
    assert not search("Mélicocq")
    process_documents(json.dumps(doc.copy()))
    assert search("Melicocq")


def test_process_should_deindex_if_action_is_given(factory):
    doc = factory(name="Mélicocq")
    assert search("Mélicoq")
    process_documents(json.dumps({"_action": "delete", "_id": doc["_id"]}))
    assert not search("Mélicoq")


def test_process_should_update_if_action_is_given(factory):
    doc = factory(name="rue de l'avoine")
    assert search("rue")
    doc["_action"] = "update"
    doc["name"] = "avenue de l'avoine"
    process_documents(json.dumps(doc.copy()))
    assert search("avenue")
    assert not search("rue")


def test_reset(factory, monkeypatch):
    class Args:
        force = False

    factory(name="rue de l'avoine")
    assert DB.keys()
    monkeypatch.setitem(__builtins__, "input", lambda *args, **kwargs: "no")
    reset(Args())
    assert DB.keys()
    monkeypatch.setitem(__builtins__, "input", lambda *args, **kwargs: "yes")
    reset(Args())
    assert not DB.keys()


def test_force_reset(factory):
    class Args:
        force = True

    factory(name="rue de l'avoine")
    assert DB.keys()
    reset(Args())
    assert not DB.keys()
