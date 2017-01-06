def token_key(s):
    return 'w|{}'.format(s)


def document_key(s):
    return 'd|{}'.format(s)


def geohash_key(s):
    return 'g|{}'.format(s)


def filter_key(k, v):
    return 'f|{}|{}'.format(k, v)
