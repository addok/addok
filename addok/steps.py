from . import config
from .db import DB


def step_only_commons(helper):
    if len(helper.tokens) == len(helper.common):
        # Only common terms, shortcut to search
        keys = [t.db_key for t in helper.tokens]
        if helper.geohash_key:
            keys.append(helper.geohash_key)
            helper.debug('Adding geohash %s', helper.geohash_key)
            helper.autocomplete(helper.tokens, use_geohash=True)
        if len(keys) == 1 or helper.geohash_key:
            helper.add_to_bucket(keys)
        if helper.bucket_dry and len(keys) > 1:
            count = 0
            # Scan the less frequent token.
            helper.tokens.sort(key=lambda t: t.frequency)
            first = helper.tokens[0]
            if first.frequency < config.INTERSECT_LIMIT:
                helper.debug('Under INTERSECT_LIMIT, brut force.')
                keys = [t.db_key for t in helper.tokens]
                helper.add_to_bucket(keys)
            else:
                helper.debug('INTERSECT_LIMIT hit, manual scan on %s', first)
                others = [t.db_key for t in helper.tokens[1:]]
                ids = DB.zrevrange(first.db_key, 0, 500)
                for id_ in ids:
                    count += 1
                    if all(DB.sismember(f, id_) for f in helper.filters) \
                       and all(DB.zrank(k, id_) for k in others):
                        helper.bucket.add(id_)
                    if helper.bucket_full:
                        break
                helper.debug('%s results after scan (%s loops)',
                             len(helper.bucket), count)
        helper.autocomplete(helper.tokens, skip_commons=True)
        if not helper.bucket_empty:
            helper.debug('Only common terms. Return.')
            return True


def step_no_meaningful_but_common_try_autocomplete(helper):
    if not helper.meaningful and helper.common:
        # Only commons terms, try to reduce with autocomplete.
        helper.debug('Only commons, trying autocomplete')
        helper.autocomplete(helper.common)
        helper.meaningful = helper.common[:1]
        if not helper.pass_should_match_threshold:
            return False
        if helper.bucket_full or helper.bucket_overflow or helper.has_cream():
            return True


def step_bucket_with_meaningful(helper):
    if len(helper.meaningful) == 1 and helper.common:
        # Avoid running with too less tokens while having commons terms.
        for token in helper.common:
            if token not in helper.meaningful:
                helper.meaningful.append(token)
                break  # We want only one more.
    helper.keys = [t.db_key for t in helper.meaningful]
    if helper.bucket_empty:
        helper.new_bucket(helper.keys, helper.SMALL_BUCKET_LIMIT)
        if not helper._autocomplete and helper.has_cream():
            # Do not check cream before computing autocomplete when
            # autocomplete is on.
            helper.debug('Cream found. Returning.')
            return True
        if len(helper.bucket) == helper.SMALL_BUCKET_LIMIT:
            # Do not rerun if bucket with limit 10 has returned less
            # than 10 results.
            helper.new_bucket(helper.keys)
    else:
        helper.add_to_bucket(helper.keys)


def step_reduce_with_other_commons(helper):
    for token in helper.common:  # Already ordered by frequency asc.
        if token not in helper.meaningful and helper.bucket_overflow:
            helper.debug('Now considering also common token %s', token)
            helper.meaningful.append(token)
            helper.keys = [t.db_key for t in helper.meaningful]
            helper.new_bucket(helper.keys)


def step_ensure_geohash_results_are_included_if_center_is_given(helper):
    if helper.bucket_overflow and helper.geohash_key:
        helper.debug('Bucket overflow and center, force nearby look up')
        helper.add_to_bucket(helper.keys + [helper.geohash_key], helper.limit)


def step_autocomplete(helper):
    if helper.bucket_overflow:
        return
    if not helper._autocomplete:
        helper.debug('Autocomplete not active. Abort.')
        return
    if helper.geohash_key:
        helper.autocomplete(helper.meaningful, use_geohash=True)
    helper.autocomplete(helper.meaningful)


def step_fuzzy(helper):
    if helper._fuzzy and not helper.has_cream():
        if helper.not_found:
            helper.fuzzy(helper.not_found)
        if helper.bucket_dry and not helper.has_cream():
            helper.fuzzy(helper.meaningful)
        if helper.bucket_dry and not helper.has_cream():
            helper.fuzzy(helper.meaningful, include_common=False)


def step_extend_results_reducing_tokens(helper):
    if helper.has_cream():
        return  # No need.
    if helper.bucket_dry:
        helper.reduce_tokens()


def step_check_bucket_full(helper):
    return helper.bucket_full


def step_check_cream(helper):
    return helper.has_cream()
