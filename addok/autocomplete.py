import redis

from addok.config import config
from addok.db import DB
from addok.helpers import keys as dbkeys
from addok.helpers import magenta, parallelize, white
from addok.helpers.index import token_key_frequency
from addok.helpers.search import preprocess_query
from addok.helpers.text import compute_edge_ngrams
from addok.pairs import pair_key


def edge_ngram_key(s):
    return 'n|{}'.format(s)


def index_edge_ngrams(pipe, token):
    for ngram in compute_edge_ngrams(token):
        pipe.sadd(edge_ngram_key(ngram), token)


def deindex_edge_ngrams(token):
    for ngram in compute_edge_ngrams(token):
        DB.srem(edge_ngram_key(ngram), token)


class EdgeNgramIndexer:

    @staticmethod
    def index(pipe, key, doc, tokens, **kwargs):
        if config.INDEX_EDGE_NGRAMS:  # Allow to disable for mass indexing.
            for token in tokens.keys():
                index_edge_ngrams(pipe, token)

    @staticmethod
    def deindex(db, key, doc, tokens, **kwargs):
        if config.INDEX_EDGE_NGRAMS:
            for token in tokens:
                tkey = dbkeys.token_key(token)
                if not DB.exists(tkey):
                    deindex_edge_ngrams(token)


def only_commons_but_geohash_try_autocomplete_collector(helper):
    if helper.geohash_key and len(helper.tokens) == len(helper.common):
        autocomplete(helper, helper.tokens, use_geohash=True)


def only_commons_try_autocomplete_collector(helper):
    if len(helper.tokens) == len(helper.common):
        autocomplete(helper, helper.tokens, skip_commons=True)
        if not helper.bucket_empty:
            helper.debug('Only common terms. Return.')
            return True


def no_meaningful_but_common_try_autocomplete_collector(helper):
    if not helper.meaningful and helper.common:
        # Only commons terms, try to reduce with autocomplete.
        helper.debug('Only commons, trying autocomplete')
        autocomplete(helper, helper.common)
        helper.meaningful = helper.common[:1]
        if not helper.pass_should_match_threshold:
            return False
        if helper.bucket_full or helper.bucket_overflow or helper.has_cream():
            return True


def autocomplete_meaningful_collector(helper):
    if helper.bucket_overflow:
        return
    if not helper.autocomplete:
        helper.debug('Autocomplete not active. Abort.')
        return
    if helper.geohash_key:
        autocomplete(helper, helper.meaningful, use_geohash=True)
    autocomplete(helper, helper.meaningful)


def autocomplete(helper, tokens, skip_commons=False, use_geohash=False):
    helper.debug('Autocompleting %s', helper.last_token)
    keys = [t.db_key for t in tokens if not t.is_last]
    pair_keys = [pair_key(t) for t in tokens if not t.is_last]
    key = edge_ngram_key(helper.last_token)
    autocomplete_tokens = DB.sinter(pair_keys + [key])
    helper.debug('Found tokens to autocomplete %s', autocomplete_tokens)
    for token in autocomplete_tokens:
        key = dbkeys.token_key(token.decode())
        if skip_commons\
           and token_key_frequency(key) > config.COMMON_THRESHOLD:
            helper.debug('Skip common token to autocomplete %s', key)
            continue
        if not helper.bucket_overflow or helper.last_token in helper.not_found:
            helper.debug('Trying to extend bucket. Autocomplete %s', key)
            extra_keys = [key]
            if use_geohash and helper.geohash_key:
                extra_keys.append(helper.geohash_key)
            helper.add_to_bucket(keys + extra_keys)


def index_ngram_keys(*keys):
    pipe = DB.pipeline(transaction=False)
    for key in keys:
        key = key.decode()
        _, token = key.split('|')
        if token.isdigit():
            continue
        index_edge_ngrams(pipe, token)
    try:
        pipe.execute()
    except redis.RedisError as e:
        msg = 'Error while generating ngrams:\n{}'.format(str(e))
        raise ValueError(msg)
    return keys


def create_edge_ngrams(*args):
    parallelize(index_ngram_keys, DB.scan_iter(match='w|*'), chunk_size=10000,
                throttle=1000)


def register_command(subparsers):
    parser = subparsers.add_parser('ngrams', help='Create edge ngrams.')
    parser.set_defaults(func=create_edge_ngrams)


def configure(config):
    config.RESULTS_COLLECTORS_PYPATHS.insert(0, only_commons_but_geohash_try_autocomplete_collector)  # noqa
    target = 'addok.helpers.collectors.only_commons'
    if target in config.RESULTS_COLLECTORS_PYPATHS:
        idx = config.RESULTS_COLLECTORS_PYPATHS.index(target)
        config.RESULTS_COLLECTORS_PYPATHS.insert(idx + 1, only_commons_try_autocomplete_collector)  # noqa
        config.RESULTS_COLLECTORS_PYPATHS.insert(idx + 1, no_meaningful_but_common_try_autocomplete_collector)  # noqa
    target = 'addok.helpers.collectors.extend_results_reducing_tokens'
    if target in config.RESULTS_COLLECTORS_PYPATHS:
        idx = config.RESULTS_COLLECTORS_PYPATHS.index(target)
        config.RESULTS_COLLECTORS_PYPATHS.insert(idx, autocomplete_meaningful_collector)  # noqa


def do_AUTOCOMPLETE(cmd, s):
    """Shows autocomplete results for a given token."""
    s = list(preprocess_query(s))[0]
    keys = [k.decode() for k in DB.smembers(edge_ngram_key(s))]
    print(white(keys))
    print(magenta('({} elements)'.format(len(keys))))


def register_shell_command(cmd):
    cmd.register_command(do_AUTOCOMPLETE)
