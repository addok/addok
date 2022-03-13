from math import ceil

from addok.config import config
from addok.helpers import iter_pipe


def preprocess_query(s):
    return list(iter_pipe(s, config.QUERY_PROCESSORS + config.PROCESSORS))


def tokenize(helper):
    helper.tokens = preprocess_query(helper.query)
    if helper.tokens:
        helper.tokens[-1].is_last = True
        helper.last_token = helper.tokens[-1]
    helper.tokens.sort(key=lambda x: len(x), reverse=True)


def search_tokens(helper):
    for token in helper.tokens:
        token.search()


def set_should_match_threshold(helper):
    helper.should_match_threshold = ceil(2 / 3 * len(helper.tokens))


def select_tokens(helper):
    tokens = []
    for token in helper.tokens:
        if token.kind == "housenumber":
            helper.housenumbers.append(token)
            continue  # Remove from tokens (housenumbers are not indexed).
        elif token.is_common:
            helper.common.append(token)
        elif token.db_key:
            helper.meaningful.append(token)
        else:
            helper.not_found.append(token)
        tokens.append(token)
    helper.tokens = tokens
    helper.common.sort(key=lambda x: x.frequency)
    helper.meaningful.sort(key=lambda x: x.frequency)
    # Sanity limit.
    helper.common.extend(helper.meaningful[helper.MAX_MEANINGFUL :])
    helper.meaningful = helper.meaningful[: helper.MAX_MEANINGFUL]
