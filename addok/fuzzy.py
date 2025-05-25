import string

from addok.db import DB
from addok.helpers import keys as dbkeys
from addok.helpers import blue, white
from addok.helpers.search import preprocess_query
from addok.helpers.text import Token
from addok.pairs import pair_key

from addok.config import config


def make_fuzzy(word, max=1):
    """Naive neighborhoods algo."""
    # inversions
    neighbors = []
    for i in range(0, len(word) - 1):
        neighbor = list(word)
        neighbor[i], neighbor[i + 1] = neighbor[i + 1], neighbor[i]
        neighbors.append("".join(neighbor))

    # limit substitutions to keyboard mapping
    if config.FUZZY_KEY_MAP is not None:
        for i in range(0, len(word)):
            neighbor = list(word)
            if neighbor[i] in config.FUZZY_KEY_MAP:
                for letter in list(config.FUZZY_KEY_MAP[neighbor[i]]):
                    if letter != neighbor[i]:
                        neighbor[i] = letter
                        neighbors.append("".join(neighbor))
    else:
        # substitutions
        for letter in string.ascii_lowercase:
            for i in range(0, len(word)):
                neighbor = list(word)
                if letter != neighbor[i]:
                    neighbor[i] = letter
                    neighbors.append("".join(neighbor))

    # insertions
    for letter in string.ascii_lowercase:
        for i in range(0, len(word) + 1):
            neighbor = list(word)
            neighbor.insert(i, letter)
            neighbors.append("".join(neighbor))

    # removal
    if len(word) > 3:
        for i in range(0, len(word)):
            neighbor = list(word)
            del neighbor[i]
            neighbors.append("".join(neighbor))

    # Order-preserving deduplication of neighbors
    neighbors = list(dict.fromkeys(neighbors))
    return neighbors


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
    helper.debug("Fuzzy on. Trying with %s.", tokens)
    tokens.sort(key=lambda t: len(t), reverse=True)
    allkeys = helper.keys[:]
    if include_common:
        # As we are in fuzzy, try to narrow as much as possible by adding
        # unused common tokens.
        allkeys.extend([t.db_key for t in helper.common if t.db_key not in helper.keys])
    for try_one in tokens:
        if helper.bucket_full:
            break
        keys = allkeys[:]
        if try_one.db_key in keys:
            keys.remove(try_one.db_key)
        if try_one.isdigit():
            continue
        helper.debug("Going fuzzy with %s and %s", try_one, keys)
        neighbors = make_fuzzy(try_one, max=helper.fuzzy)
        if len(keys):
            # Only retain tokens that have been seen in the index at least
            # once with the other tokens.
            DB.sadd(helper.pid, *neighbors)
            interkeys = [pair_key(k[2:]) for k in keys]
            interkeys.append(helper.pid)
            fuzzy_words = DB.sinter(interkeys)
            DB.delete(helper.pid)
            # Keep the priority we gave in building fuzzy terms (inversion
            # first, then substitution, etc.).
            fuzzy_words = [w.decode() for w in fuzzy_words]
            fuzzy_words.sort(key=lambda x: neighbors.index(x))
        else:
            # The token we are considering is alone.
            fuzzy_words = []
            for neighbor in neighbors:
                key = dbkeys.token_key(neighbor)
                count = DB.zcard(key)
                if count:
                    fuzzy_words.append(neighbor)
        if fuzzy_words:
            helper.debug("Found fuzzy candidates %s", fuzzy_words)
            fuzzy_keys = [dbkeys.token_key(w) for w in fuzzy_words]
            for key in fuzzy_keys:
                if helper.bucket_dry:
                    helper.add_to_bucket(keys + [key])


def do_fuzzy(self, word):
    """Compute fuzzy extensions of word.
    FUZZY lilas"""
    word = list(preprocess_query(word))[0]
    fuzzy = make_fuzzy(word)
    print(white(fuzzy))
    print(blue("{} items".format(len(fuzzy))))


def do_fuzzyindex(self, word):
    """Compute fuzzy extensions of word that exist in index.
    FUZZYINDEX lilas"""
    word = list(preprocess_query(word))[0]
    token = Token(word)
    neighbors = make_fuzzy(token)
    neighbors = [(n, DB.zcard(dbkeys.token_key(n))) for n in neighbors]
    neighbors.sort(key=lambda n: n[1], reverse=True)
    for token, freq in neighbors:
        if freq == 0:
            break
        print(white(token), blue(freq))


def register_shell_command(cmd):
    cmd.register_commands(do_fuzzy, do_fuzzyindex)
