from addok.config import config
from addok.db import DB
from addok.helpers import keys


class RedisStore:

    def get(self, *keys):
        pipe = DB.pipeline(transaction=False)
        for key in keys:
            pipe.get(key)
        for doc in pipe.execute():
            if doc is not None:
                yield doc

    def add(self, *docs):
        pipe = DB.pipeline(transaction=False)
        for key, blob in docs:
            pipe.set(key, blob)
        pipe.execute()

    def remove(self, *keys):
        pipe = DB.pipeline(transaction=False)
        for key in keys:
            pipe.delete(key)
        pipe.execute()


class DSProxy:
    instance = None

    def __getattr__(self, name):
        return getattr(self.instance, name)


DS = DSProxy()


@config.on_load
def on_load():
    DS.instance = config.DOCUMENT_STORE()


def store_documents(docs):
    to_add = []
    to_remove = []
    for doc in docs:
        key = keys.document_key(doc['id'])
        if doc.get('_action') in ['delete', 'update']:
            to_remove.append(key)
        if doc.get('_action') in ['index', 'update', None]:
            to_add.append((key, config.DOCUMENT_SERIALIZER.dumps(doc)))
        yield doc
    if to_remove:
        DS.remove(*to_remove)
    if to_add:
        DS.add(*to_add)


def get_document(key):
    raw = list(DS.get(key))
    if raw:
        return config.DOCUMENT_SERIALIZER.loads(raw[0])


def get_documents(*keys):
    for raw in DS.get(*keys):
        yield config.DOCUMENT_SERIALIZER.loads(raw)
