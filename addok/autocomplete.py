import time
from multiprocessing import Pool

from addok import config, hooks
from addok.db import DB
from addok.helpers.index import token_key, token_key_frequency
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


def edge_ngram_indexer(pipe, key, doc, tokens, **kwargs):
    if config.INDEX_EDGE_NGRAMS:  # Allow to disable for mass indexing.
        for token in tokens.keys():
            index_edge_ngrams(pipe, token)


def edge_ngram_deindexer(db, key, doc, tokens, **kwargs):
    if config.INDEX_EDGE_NGRAMS:
        for token in tokens:
            tkey = token_key(token)
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
    # helper.last_token.autocomplete()
    keys = [t.db_key for t in tokens if not t.is_last]
    pair_keys = [pair_key(t) for t in tokens if not t.is_last]
    key = edge_ngram_key(helper.last_token)
    autocomplete_tokens = DB.sinter(pair_keys + [key])
    helper.debug('Found tokens to autocomplete %s', autocomplete_tokens)
    for token in autocomplete_tokens:
        key = token_key(token.decode())
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


def index_ngram_key(key):
    key = key.decode()
    _, token = key.split('|')
    if token.isdigit():
        return
    index_edge_ngrams(DB, token)


def create_edge_ngrams(*args):
    start = time.time()
    pool = Pool()
    count = 0
    chunk = []
    for key in DB.scan_iter(match='w|*'):
        count += 1
        chunk.append(key)
        if count % 10000 == 0:
            pool.map(index_ngram_key, chunk)
            print("Done", count, time.time() - start)
            chunk = []
    if chunk:
        pool.map(index_ngram_key, chunk)
    pool.close()
    pool.join()
    print('Done', count, 'in', time.time() - start)


@hooks.register
def addok_register_command(subparsers):
    parser = subparsers.add_parser('ngrams', help='Create edge ngrams.')
    parser.set_defaults(func=create_edge_ngrams)


@hooks.register
def addok_configure(config):
    config.RESULTS_COLLECTORS.insert(0, only_commons_but_geohash_try_autocomplete_collector)  # noqa
    target = 'addok.helpers.collectors.only_commons'
    if target in config.RESULTS_COLLECTORS:
        idx = config.RESULTS_COLLECTORS.index(target)
        config.RESULTS_COLLECTORS.insert(idx + 1, only_commons_try_autocomplete_collector)  # noqa
        config.RESULTS_COLLECTORS.insert(idx + 1, no_meaningful_but_common_try_autocomplete_collector)  # noqa
    target = 'addok.helpers.collectors.extend_results_reducing_tokens'
    if target in config.RESULTS_COLLECTORS:
        idx = config.RESULTS_COLLECTORS.index(target)
        config.RESULTS_COLLECTORS.insert(idx, autocomplete_meaningful_collector)  # noqa
    target = 'addok.helpers.index.fields_indexer'
    if target in config.INDEXERS:
        idx = config.INDEXERS.index(target)
        config.INDEXERS.insert(idx + 1, edge_ngram_indexer)
    target = 'addok.helpers.index.fields_deindexer'
    if target in config.DEINDEXERS:
        idx = config.DEINDEXERS.index(target)
        config.DEINDEXERS.insert(idx + 1, edge_ngram_deindexer)
