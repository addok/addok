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
        tokens = list(set(tokens.keys()))  # Unique values.
        housenumber_pairs = set()
        housenumbers = doc.get(config.HOUSENUMBERS_FIELD)
        if housenumbers:
            for number in housenumbers.keys():
                for token in preprocess(number):
                    # Pair every document term to each housenumber, but do not
                    # pair housenumbers together.
                    pipe.sadd(pair_key(token), *tokens)
                    housenumber_pairs.add(token)
        for token in tokens:
            pairs = set(t for t in tokens if t != token)
            pairs.update(housenumber_pairs)
            if pairs:
                pipe.sadd(pair_key(token), *pairs)

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        housenumbers = doc.get('housenumbers', {})
        tokens = list(set(tokens + list(housenumbers.keys())))  # Deduplicate.
        for i, token in enumerate(tokens):
            for token2 in tokens[i:]:
                if token != token2:
                    tmp_key = '|'.join(['didx', token, token2])
                    # Do we have other documents that share token and token2?
                    commons = db.zinterstore(tmp_key, [keys.token_key(token),
                                                       keys.token_key(token2)])
                    db.delete(tmp_key)
                    if not commons:
                        db.srem(pair_key(token), token2)
                        db.srem(pair_key(token2), token)


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
