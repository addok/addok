from addok.config import config
from addok.db import DB
from addok.helpers import scripts


def only_commons(helper):
    if len(helper.tokens) == len(helper.common):
        # Only common terms, shortcut to search
        keys = [t.db_key for t in helper.tokens]
        if helper.geohash_key:
            keys.append(helper.geohash_key)
            helper.debug('Adding geohash %s', helper.geohash_key)
        if len(keys) == 1 or helper.geohash_key:
            helper.add_to_bucket(keys)
        if helper.bucket_dry and len(keys) > 1:
            # Scan the less frequent token.
            helper.tokens.sort(key=lambda t: t.frequency)
            keys = [t.db_key for t in helper.tokens]
            first = helper.tokens[0]
            if first.frequency < config.INTERSECT_LIMIT:
                helper.debug('Under INTERSECT_LIMIT, force intersect.')
                helper.add_to_bucket(keys)
            else:
                helper.debug('INTERSECT_LIMIT hit, manual scan')
                if helper.filters:
                    # Always consider filters when doing manual intersect.
                    keys = keys + helper.filters
                    # But, hey, can we brute force again?
                    if any(DB.scard(k) < config.INTERSECT_LIMIT
                           for k in helper.filters):
                        helper.debug('Filters under INTERSECT_LIMIT, force')
                        helper.add_to_bucket(keys)
                        return
                helper.debug('manual scan on "%s"', first)
                ids = scripts.manual_scan(keys=keys, args=[helper.wanted])
                helper.bucket.update(ids)
                helper.debug('%s results after scan', len(helper.bucket))


def bucket_with_meaningful(helper):
    if not helper.meaningful:
        return
    if len(helper.meaningful) == 1 and helper.common:
        # Avoid running with too less tokens while having commons terms.
        for token in helper.common:
            if token not in helper.meaningful:
                helper.meaningful.append(token)
                break  # We want only one more.
    helper.keys = [t.db_key for t in helper.meaningful]
    if helper.bucket_empty:
        helper.new_bucket(helper.keys, config.BUCKET_MIN)
        if (not helper.autocomplete and helper.has_cream() and
                helper.cream < config.BUCKET_MIN):
            # Do not check cream before computing autocomplete when
            # autocomplete is on.
            # If we have too much cream, do not consider our bucket is good.
            helper.debug('Cream found. Returning.')
            return True
        if len(helper.bucket) == config.BUCKET_MIN:
            # Do not rerun if bucket with limit 10 has returned less
            # than 10 results.
            helper.new_bucket(helper.keys)
    else:
        helper.add_to_bucket(helper.keys)


def reduce_with_other_commons(helper):
    if len(helper.tokens) == len(helper.common):
        return
    for token in helper.common:  # Already ordered by frequency asc.
        if token not in helper.meaningful and helper.bucket_overflow:
            helper.debug('Now considering also common token %s', token)
            helper.meaningful.append(token)
            helper.keys = [t.db_key for t in helper.meaningful]
            helper.new_bucket(helper.keys)


def ensure_geohash_results_are_included_if_center_is_given(helper):
    if helper.bucket_overflow and helper.geohash_key:
        helper.debug('Bucket overflow and center, force nearby look up')
        helper.add_to_bucket(helper.keys + [helper.geohash_key], helper.wanted)


def extend_results_reducing_tokens(helper):
    if helper.bucket_full or helper.has_cream():
        return True
    if not helper.bucket_dry:
        return  # No need.
    # Only if bucket is empty or we have margin on should_match_threshold.
    if (helper.bucket_empty
            or len(helper.meaningful) - 1 > helper.should_match_threshold):
        helper.debug('Bucket dry. Trying to remove some tokens.')

        def sorter(t):
            # First numbers, then by frequency
            return (2 if t.isdigit() else 1, t.frequency)

        helper.meaningful.sort(key=sorter, reverse=True)
        for token in helper.meaningful:
            keys = helper.keys[:]
            keys.remove(token.db_key)
            helper.add_to_bucket(keys)
            if helper.bucket_overflow:
                break
