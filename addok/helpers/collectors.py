from addok.config import config


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
                ids = config.DB.zrevrange(first.db_key, 0, 500)
                for id_ in ids:
                    count += 1
                    if (all(config.DB.sismember(f, id_) for f in helper.filters)
                       and all(config.DB.zrank(k, id_) for k in others)):
                        helper.bucket.add(id_)
                    if helper.bucket_full:
                        break
                helper.debug('%s results after scan (%s loops)',
                             len(helper.bucket), count)


def bucket_with_meaningful(helper):
    if len(helper.meaningful) == 1 and helper.common:
        # Avoid running with too less tokens while having commons terms.
        for token in helper.common:
            if token not in helper.meaningful:
                helper.meaningful.append(token)
                break  # We want only one more.
    helper.keys = [t.db_key for t in helper.meaningful]
    if helper.bucket_empty:
        helper.new_bucket(helper.keys, helper.SMALL_BUCKET_LIMIT)
        if (not helper.autocomplete and helper.cream > 0 and
                helper.cream < helper.SMALL_BUCKET_LIMIT):
            # Do not check cream before computing autocomplete when
            # autocomplete is on.
            # If we have too much cream, do not consider our bucket is good.
            helper.debug('Cream found. Returning.')
            return True
        if len(helper.bucket) == helper.SMALL_BUCKET_LIMIT:
            # Do not rerun if bucket with limit 10 has returned less
            # than 10 results.
            helper.new_bucket(helper.keys)
    else:
        helper.add_to_bucket(helper.keys)


def reduce_with_other_commons(helper):
    for token in helper.common:  # Already ordered by frequency asc.
        if token not in helper.meaningful and helper.bucket_overflow:
            helper.debug('Now considering also common token %s', token)
            helper.meaningful.append(token)
            helper.keys = [t.db_key for t in helper.meaningful]
            helper.new_bucket(helper.keys)


def ensure_geohash_results_are_included_if_center_is_given(helper):
    if helper.bucket_overflow and helper.geohash_key:
        helper.debug('Bucket overflow and center, force nearby look up')
        helper.add_to_bucket(helper.keys + [helper.geohash_key], helper.limit)


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
