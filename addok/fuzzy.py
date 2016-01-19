from addok import hooks
from addok.db import DB
from addok.helpers.index import token_key
from addok.pairs import pair_key
from addok.helpers.text import make_fuzzy


def fuzzy_collector(helper):
    if helper.fuzzy and not helper.has_cream():
        if helper.not_found:
            try_fuzzy(helper, helper.not_found)
        if helper.bucket_dry and not helper.has_cream():
            try_fuzzy(helper, helper.meaningful)
        if helper.bucket_dry and not helper.has_cream() and helper.common:
            try_fuzzy(helper, helper.meaningful, include_common=False)


def try_fuzzy(helper, tokens, include_common=True):
    if not helper.bucket_dry or not tokens:
        return
    helper.debug('Fuzzy on. Trying with %s.', tokens)
    tokens.sort(key=lambda t: len(t), reverse=True)
    allkeys = helper.keys[:]
    if include_common:
        # As we are in fuzzy, try to narrow as much as possible by adding
        # unused commons tokens.
        common = [t for t in helper.common if t.db_key not in helper.keys]
        allkeys.extend([t.db_key for t in common])
    for try_one in tokens:
        if helper.bucket_full:
            break
        keys = allkeys[:]
        if try_one.db_key in keys:
            keys.remove(try_one.db_key)
        if try_one.isdigit():
            continue
        helper.debug('Going fuzzy with %s', try_one)
        neighbors = make_fuzzy(try_one.original, max=helper.fuzzy)
        if len(keys):
            # Only retains tokens that have been seen in the index at least
            # once with the other tokens.
            DB.sadd(helper.query, *neighbors)
            interkeys = [pair_key(k[2:]) for k in keys]
            interkeys.append(helper.query)
            fuzzy_words = DB.sinter(interkeys)
            DB.delete(helper.query)
            # Keep the priority we gave in building fuzzy terms (inversion
            # first, then substitution, etc.).
            fuzzy_words = [w.decode() for w in fuzzy_words]
            fuzzy_words.sort(key=lambda x: neighbors.index(x))
        else:
            # The token we are considering is alone.
            fuzzy_words = []
            for neighbor in neighbors:
                key = token_key(neighbor)
                count = DB.zcard(key)
                if count:
                    fuzzy_words.append(neighbor)
        helper.debug('Found fuzzy candidates %s', fuzzy_words)
        fuzzy_keys = [token_key(w) for w in fuzzy_words]
        for key in fuzzy_keys:
            if helper.bucket_dry:
                helper.add_to_bucket(keys + [key])


@hooks.register
def addok_configure(config):
    target = 'addok.helpers.collectors.extend_results_reducing_tokens'
    if target in config.RESULTS_COLLECTORS:
        idx = config.RESULTS_COLLECTORS.index(target)
        config.RESULTS_COLLECTORS.insert(idx, 'addok.fuzzy.fuzzy_collector')
