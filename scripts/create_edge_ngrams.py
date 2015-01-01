from addok.core import DB
from addok.index_utils import index_edge_ngrams


def main():
    for key in DB.scan_iter(match='w|*'):
        key = key.decode()
        _, token = key.split('|')
        if token.isdigit():
            continue
        index_edge_ngrams(token)


if __name__ == '__main__':
    main()
