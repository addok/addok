from collections import defaultdict
from itertools import product

from addok.config import config
from addok.db import DB
from addok.helpers import scripts
from addok.pairs import pair_key


def no_tokens_but_housenumbers_and_geohash(helper):
    if not helper.tokens and helper.housenumbers and helper.geohash_key:
        helper.new_bucket([helper.geohash_key], config.BUCKET_MIN)


def no_available_tokens_abort(helper):
    if not helper.tokens:
        return True  # Stop processing.


def only_commons(helper):
    if helper.only_commons:
        # Only common terms, shortcut to search
        keys = [t.db_key for t in helper.tokens]
        if helper.geohash_key:
            keys.append(helper.geohash_key)
            helper.debug("Adding geohash %s", helper.geohash_key)
        if len(keys) == 1 or helper.geohash_key:
            helper.add_to_bucket(keys)
        if helper.bucket_dry and len(keys) > 1:
            # Scan the less frequent token.
            helper.tokens.sort(key=lambda t: t.frequency)
            keys = [t.db_key for t in helper.tokens]
            first = helper.tokens[0]
            
            if first.frequency < config.INTERSECT_LIMIT:
                # Case 1: Token is small enough → use Redis intersect
                helper.debug("Under INTERSECT_LIMIT, force intersect.")
                helper.add_to_bucket(keys)
            elif helper.filters:
                # Case 2: Token is large BUT we have filters to consider
                all_keys = keys + helper.filters
                min_filter_size = min(DB.scard(k) for k in helper.filters)
                
                if min_filter_size < first.frequency:
                    # Filter is more selective than token → use Redis intersect
                    helper.debug(
                        "Filter (%s) more selective than token (%s), use intersect",
                        min_filter_size, first.frequency
                    )
                    helper.add_to_bucket(all_keys)
                else:
                    # Both token and filter are large → manual scan
                    helper.debug(
                        "Token (%s) and filter (%s) both large, manual scan",
                        first.frequency, min_filter_size
                    )
                    ids = scripts.manual_scan(keys=all_keys, args=[helper.wanted])
                    helper.bucket.update(ids)
                    helper.debug("%s results after scan", len(helper.bucket))
            else:
                # Case 3: Token is large, no filter → manual scan
                helper.debug("INTERSECT_LIMIT hit, manual scan on '%s'", first)
                ids = scripts.manual_scan(keys=keys, args=[helper.wanted])
                helper.bucket.update(ids)
                helper.debug("%s results after scan", len(helper.bucket))


def bucket_with_meaningful(helper):
    if not helper.meaningful:
        return
    if len(helper.meaningful) == 1 and helper.common and not helper.filters:
        # Avoid running with too less tokens while having commons terms.
        for token in helper.common:
            if token not in helper.meaningful:
                helper.meaningful.append(token)
                break  # We want only one more.
    helper.keys = [t.db_key for t in helper.meaningful]
    if helper.bucket_empty:
        helper.new_bucket(helper.keys, config.BUCKET_MIN)
        if len(helper.bucket) == config.BUCKET_MIN:
            # Do not rerun if bucket with limit 10 has returned less
            # than 10 results.
            helper.new_bucket(helper.keys)
        if (
            not helper.autocomplete
            and helper.has_cream()
            and helper.cream < config.BUCKET_MIN
        ):
            # Do not check cream before computing autocomplete when
            # autocomplete is on.
            # If we have too much cream, do not consider our bucket is good.
            helper.debug("Cream found. Returning.")
            return True
    else:
        helper.add_to_bucket(helper.keys)


def reduce_with_other_commons(helper):
    if helper.only_commons:
        return
    for token in helper.common:  # Already ordered by frequency asc.
        if token not in helper.meaningful and helper.bucket_overflow:
            helper.debug("Now considering also common token %s", token)
            helper.meaningful.append(token)
            helper.keys = [t.db_key for t in helper.meaningful]
            helper.new_bucket(helper.keys)


def ensure_geohash_results_are_included_if_center_is_given(helper):
    if helper.bucket_overflow and helper.geohash_key:
        helper.debug("Bucket overflow and center, force nearby look up")
        helper.add_to_bucket(helper.keys + [helper.geohash_key], max(helper.wanted, 10))


def extend_results_reducing_tokens(helper):
    if helper.bucket_full or helper.has_cream():
        return True
    if not helper.bucket_dry:
        return  # No need.
    # Only if bucket is empty or we have margin on should_match_threshold.
    if (
        helper.bucket_empty
        or len(helper.meaningful) - 1 > helper.should_match_threshold
    ):
        helper.debug("Bucket dry. Trying to remove 1 meaningful token.")

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

        if helper.bucket_empty and len(helper.meaningful) > 3:
            helper.debug("Bucket still empty, remove 2 meaningful tokens.")
            for token, token2 in product(helper.meaningful, helper.meaningful):
                if token != token2:
                    keys = helper.keys[:]
                    keys.remove(token.db_key)
                    keys.remove(token2.db_key)
                    helper.add_to_bucket(keys)
                    if helper.bucket_overflow:
                        break


def extend_results_extrapoling_relations(helper):
    """Try to extract the bigger group of interlinked tokens.

    Should generally be used at last in the collectors chain.
    """
    if not helper.bucket_dry:
        return  # No need.

    tokens = set(helper.meaningful + helper.common)

    # Sort by average frequency. Needed since we are going to break the loop and we want determinism.
    relations = sorted(
        _extract_manytomany_relations(tokens),
        key=lambda r: sum(t.frequency for t in r) / len(r) if len(r) > 0 else 0
    )

    for relation in relations:
        helper.add_to_bucket([t.db_key for t in relation])
        if helper.bucket_overflow:
            break
    else:
        helper.debug("No relation extrapolated.")


def _extract_manytomany_relations(tokens):
    o2m_relations = _compute_onetomany_relations(tokens)
    m2m_relations = _extrapolate_manytomany_relations(o2m_relations)
    return _deduplicate_sets(m2m_relations)


def _compute_onetomany_relations(tokens):
    relations = defaultdict(list)
    for token in tokens:
        for other in tokens:
            if other == token:
                continue
            if token in relations[other] or DB.sismember(pair_key(token), other):
                relations[token].append(other)
    return relations


def _extrapolate_manytomany_relations(o2m_relations):
    m2m_relations = []
    for origin, others in o2m_relations.items():
        relation = [origin]
        for token in others:
            if all(token in o2m_relations[o] for o in relation):
                relation.append(token)
        # Commons tokens, given that they are "common", are more luckily to
        # create false positives (but we kept them until now because if some
        # other token is not related to some common token, that is a clear true
        # negative).
        relation = set([token for token in relation if not token.is_common])
        if len(relation) > 1:
            m2m_relations.append(relation)
    return m2m_relations


def _deduplicate_sets(sets):
    unique = []
    for set_ in sorted(sets, key=len, reverse=True):
        if not any(set_.issubset(g) for g in unique):
            unique.append(set_)
    return unique
