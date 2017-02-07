from addok.config import config
from addok.db import DB
from addok.helpers import keys, magenta, white
from addok.helpers.index import preprocess
from addok.helpers.search import preprocess_query


def pair_key(s):
    return 'p|{}'.format(s)


class PairsIndexer:

    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        els = set(tokens.keys())  # Unique values.
        for el in els:
            values = set([])
            for el2 in els:
                if el != el2:
                    values.add(el2)
            if values:
                pipe.sadd(pair_key(el), *values)

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        els = list(set(tokens))  # Unique values.
        loop = 0
        for el in els:
            for el2 in els[loop:]:
                if el != el2:
                    key = '|'.join(['didx', el, el2])
                    # Do we have other documents that share el and el2?
                    commons = db.zinterstore(key, [keys.token_key(el),
                                                   keys.token_key(el2)])
                    db.delete(key)
                    if not commons:
                        db.srem(pair_key(el), el2)
                        db.srem(pair_key(el2), el)
            loop += 1


class HousenumbersPairsIndexer:

    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        housenumbers = doc.get(config.HOUSENUMBERS_FIELD)
        if not housenumbers:
            return
        for number in housenumbers.keys():
            for hn in preprocess(number):
                # Pair every document term to each housenumber, but do not pair
                # housenumbers together.
                pipe.sadd(pair_key(hn), *tokens.keys())

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        housenumbers = doc.get('housenumbers', {})
        for hn, data in housenumbers.items():
            for token in tokens:
                k = '|'.join(['didx', hn, token])
                commons = db.zinterstore(k, [keys.token_key(hn),
                                             keys.token_key(token)])
                db.delete(k)
                if not commons:
                    db.srem(pair_key(hn), token)
                    db.srem(pair_key(token), hn)


def pair(word):
    """See all token associated with a given token.
    PAIR lilas"""
    word = list(preprocess_query(word))[0]
    key = pair_key(word)
    tokens = [t.decode() for t in DB.smembers(key)]
    tokens.sort()
    print(white(tokens))
    print(magenta('(Total: {})'.format(len(tokens))))


def register_shell_command(cmd):
    cmd.register_command(pair)
