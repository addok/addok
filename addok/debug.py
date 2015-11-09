import atexit
import inspect
import json
import logging
import re
import readline
import time
from pathlib import Path

import geohash

from . import config
from .core import (Search, SearchResult, Token, compute_geohash_key,
                   make_fuzzy, preprocess_query, reverse, token_frequency)
from .db import DB
from .index_utils import VALUE_SEPARATOR, document_key, pair_key, token_key
from .textutils.default import compare_ngrams
from .utils import (blue, cyan, green, haversine_distance, km_to_score,
                    magenta, red, white, yellow)


def doc_by_id(_id):
    return DB.hgetall(document_key(_id))


def indexed_string(s):
    return list(preprocess_query(s))


def word_frequency(word):
    try:
        token = list(preprocess_query(word))[0]
    except IndexError:
        # Word has been filtered out.
        return
    return token_frequency(token)


def set_debug():
    logging.basicConfig(level=logging.DEBUG)


class Cli(object):

    HISTORY_FILE = '.cli_history'

    def __init__(self):
        self._inspect_commands()
        readline.set_completer(self.completer)
        readline.parse_and_bind("tab: complete")
        self._init_history_file()

    def _inspect_commands(self):
        self.COMMANDS = {}
        for name, func in inspect.getmembers(Cli, inspect.isfunction):
            if name.startswith('do_'):
                self.COMMANDS[name[3:].upper()] = func.__doc__ or ''

    def _init_history_file(self):
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(self.history_file)
            except FileNotFoundError:
                pass
            atexit.register(self.save_history)

    def save_history(self):
        readline.write_history_file(self.history_file)

    @property
    def history_file(self):
        return str(Path(config.LOG_DIR).joinpath(self.HISTORY_FILE))

    def completer(self, text, state):
        for cmd in self.COMMANDS.keys():
            if cmd.startswith(text.upper()):
                if not state:
                    return cmd + " "
                else:
                    state -= 1

    def error(self, message):
        print(red(message))

    @staticmethod
    def _match_option(key, string):
        matchs = re.findall('{} [^A-Z]*'.format(key), string)
        option = None
        if matchs:
            option = matchs[0]
            string = string.replace(option, '')
            option = option.replace(key, '')
        return string.strip(), option.strip() if option else option

    def _search(self, query, verbose=False, bucket=False):
        start = time.time()
        limit = 10
        autocomplete = True
        lat = None
        lon = None
        filters = {}
        if 'AUTOCOMPLETE' in query:
            query, autocomplete = self._match_option('AUTOCOMPLETE', query)
            autocomplete = bool(int(autocomplete))
        if 'LIMIT' in query:
            query, limit = self._match_option('LIMIT', query)
            limit = int(limit)
        if 'CENTER' in query:
            query, center = self._match_option('CENTER', query)
            lat, lon = center.split()
            lat = float(lat)
            lon = float(lon)
        for name in config.FILTERS:
            name = name.upper()
            if name in query:
                query, value = self._match_option(name, query)
                filters[name.lower()] = value.strip()
        helper = Search(limit=limit, verbose=verbose,
                        autocomplete=autocomplete)
        results = helper(query, lat=lat, lon=lon, **filters)
        if bucket:  # Means we want all the bucket
            results = helper._sorted_bucket

        def format_scores(result):
            if verbose or bucket:
                return (', '.join('{}: {}/{}'.format(k, round(v[0], 4), v[1])
                        for k, v in result._scores.items()))
            else:
                return result.score

        for result in results:
            print('{} ({} | {})'.format(white(result),
                                        blue(result.id),
                                        blue(format_scores(result))))
        duration = round((time.time() - start) * 1000, 1)
        formatter = red if duration > 50 else green
        print(formatter("{} ms".format(duration)), '/',
              cyan('{} results'.format(len(results))))

    def do_search(self, query):
        """Issue a search (default command, can be omitted):
        SEARCH rue des Lilas [CENTER lat lon] [LIMIT 10]"""
        self._search(query)

    def do_explain(self, query):
        """Issue a search with debug info:
        EXPLAIN rue des Lilas"""
        self._search(query, verbose=True)

    def do_bucket(self, query):
        """Issue a search and return all the collected bucket, not only up to
        limit elements:
        BUCKET rue des Lilas"""
        self._search(query, bucket=True)

    def do_tokenize(self, string):
        """Inspect how a string is tokenized before being indexed.
        TOKENIZE Rue des Lilas"""
        print(white(' '.join(indexed_string(string))))

    def do_help(self, *args):
        """Display this help message."""
        for name, doc in sorted(self.COMMANDS.items(), key=lambda x: x[0]):
            print(yellow(name),
                  cyan(doc.replace(' ' * 8, ' ').replace('\n', '')))

    def do_get(self, _id):
        """Get document from index with its id.
        GET 772210180J"""
        doc = doc_by_id(_id)
        if not doc:
            return self.error('id "{}" not found'.format(_id))
        housenumbers = {}
        for key, value in doc.items():
            key = key.decode()
            value = value.decode()
            if key.startswith('h|'):
                housenumbers[key] = value
            else:
                print(white(key),
                      magenta(', '.join(value.split(VALUE_SEPARATOR))))
        if housenumbers:
            def sorter(item):
                k, v = item
                return int(re.match(r'\d+', v.split('|')[0]).group())
            housenumbers = sorted(housenumbers.items(), key=sorter)
            housenumbers = ['{}: {}'.format(k[2:], v) for k, v in housenumbers]
            print(white('housenumbers'), magenta(', '.join(housenumbers)))

    def do_frequency(self, word):
        """Return word frequency in index.
        FREQUENCY lilas"""
        print(white(word_frequency(word)))

    def do_autocomplete(self, s):
        """Shows autocomplete results for a given token."""
        s = list(preprocess_query(s))[0]
        token = Token(s)
        token.autocomplete()
        keys = [k.split('|')[1] for k in token.autocomplete_keys]
        print(white(keys))
        print(magenta('({} elements)'.format(len(keys))))

    def _print_field_index_details(self, field, _id):
        for token in indexed_string(field):
            print(
                white(token),
                blue(DB.zscore(token_key(token), document_key(_id))),
                blue(DB.zrevrank(token_key(token), document_key(_id))),
            )

    def do_index(self, _id):
        """Get index details for a document by its id.
        INDEX 772210180J"""
        doc = doc_by_id(_id)
        if not doc:
            return self.error('id "{}" not found'.format(_id))
        for field in config.FIELDS:
            key = field['key'].encode()
            if key in doc:
                self._print_field_index_details(doc[key].decode(), _id)

    def do_bestscore(self, word):
        """Return document linked to word with higher score.
        BESTSCORE lilas"""
        key = token_key(indexed_string(word)[0])
        for _id, score in DB.zrevrange(key, 0, 20, withscores=True):
            result = SearchResult(_id)
            print(white(result), blue(score), blue(result.id))

    def do_reverse(self, latlon):
        """Do a reverse search. Args: lat lon.
        REVERSE 48.1234 2.9876"""
        lat, lon = latlon.split()
        for r in reverse(float(lat), float(lon)):
            print('{} ({} | {} km | {})'.format(white(r), blue(r.score),
                                                blue(r.distance), blue(r.id)))

    def do_pair(self, word):
        """See all token associated with a given token.
        PAIR lilas"""
        word = list(preprocess_query(word))[0]
        key = pair_key(word)
        tokens = [t.decode() for t in DB.smembers(key)]
        tokens.sort()
        print(white(tokens))
        print(magenta('(Total: {})'.format(len(tokens))))

    def do_distance(self, s):
        """Print the distance score between two strings. Use | as separator.
        DISTANCE rue des lilas|porte des lilas"""
        s = s.split('|')
        if not len(s) == 2:
            print(red('Malformed string. Use | between the two strings.'))
            return
        one, two = s
        print(white(compare_ngrams(one, two)))

    def do_dbinfo(self, *args):
        """Print some useful infos from Redis DB."""
        info = DB.info()
        keys = [
            'keyspace_misses', 'keyspace_hits', 'used_memory_human',
            'total_commands_processed', 'total_connections_received',
            'connected_clients']
        for key in keys:
            print('{}: {}'.format(white(key), blue(info[key])))
        if 'db0' in info:
            print('{}: {}'.format(white('nb keys'), blue(info['db0']['keys'])))

    def do_dbkey(self, key):
        """Print raw content of a DB key.
        DBKEY g|u09tyzfe"""
        type_ = DB.type(key).decode()
        if type_ == 'set':
            out = DB.smembers(key)
        elif type_ == 'hash':
            out = DB.hgetall(key)
        else:
            out = 'Unsupported type {}'.format(type_)
        print('type:', magenta(type_))
        print('value:', white(out))

    def do_geodistance(self, s):
        """Compute geodistance from a result to a point.
        GEODISTANCE 772210180J 48.1234 2.9876"""
        try:
            _id, lat, lon = s.split()
        except:
            return self.error('Malformed query. Use: ID lat lon')
        try:
            result = SearchResult(document_key(_id))
        except ValueError as e:
            return self.error(e)
        center = (float(lat), float(lon))
        km = haversine_distance((float(result.lat), float(result.lon)), center)
        score = km_to_score(km)
        print('km: {} | score: {}'.format(white(km), blue(score)))

    def do_geohashtogeojson(self, geoh):
        """Build GeoJSON corresponding to geohash given as parameter.
        GEOHASHTOGEOJSON u09vej04 [NEIGHBORS 0|1|2]"""
        geoh, with_neighbors = self._match_option('NEIGHBORS', geoh)
        bbox = geohash.bbox(geoh)
        try:
            with_neighbors = int(with_neighbors)
        except TypeError:
            with_neighbors = 0

        def expand(bbox, geoh, depth):
            neighbors = geohash.neighbors(geoh)
            for neighbor in neighbors:
                other = geohash.bbox(neighbor)
                if with_neighbors > depth:
                    expand(bbox, neighbor, depth + 1)
                else:
                    if other['n'] > bbox['n']:
                        bbox['n'] = other['n']
                    if other['s'] < bbox['s']:
                        bbox['s'] = other['s']
                    if other['e'] > bbox['e']:
                        bbox['e'] = other['e']
                    if other['w'] < bbox['w']:
                        bbox['w'] = other['w']

        if with_neighbors > 0:
            expand(bbox, geoh, 0)

        geojson = {
            "type": "Polygon",
            "coordinates": [[
                [bbox['w'], bbox['n']],
                [bbox['e'], bbox['n']],
                [bbox['e'], bbox['s']],
                [bbox['w'], bbox['s']],
                [bbox['w'], bbox['n']]
            ]]
        }
        print(white(json.dumps(geojson)))

    def do_geohash(self, latlon):
        """Compute a geohash from latitude and longitude.
        GEOHASH 48.1234 2.9876"""
        try:
            lat, lon = map(float, latlon.split())
        except ValueError:
            print(red('Invalid lat and lon {}'.format(latlon)))
        else:
            print(white(geohash.encode(lat, lon, config.GEOHASH_PRECISION)))

    def do_geohashmembers(self, geoh):
        """Return members of a geohash and its neighbors.
        GEOHASHMEMBERS u09vej04 [NEIGHBORS 0]"""
        geoh, with_neighbors = self._match_option('NEIGHBORS', geoh)
        key = compute_geohash_key(geoh, with_neighbors != '0')
        if key:
            for id_ in DB.smembers(key):
                r = SearchResult(id_)
                print(white(r), blue(r.id))

    def do_fuzzy(self, word):
        """Compute fuzzy extensions of word.
        FUZZY lilas"""
        word = list(preprocess_query(word))[0]
        print(white(make_fuzzy(word)))

    def do_fuzzyindex(self, word):
        """Compute fuzzy extensions of word that exist in index.
        FUZZYINDEX lilas"""
        word = list(preprocess_query(word))[0]
        token = Token(word)
        token.make_fuzzy()
        neighbors = [(n, DB.zcard(token_key(n))) for n in token.neighbors]
        neighbors.sort(key=lambda n: n[1], reverse=True)
        for token, freq in neighbors:
            if freq == 0:
                break
            print(white(token), blue(freq))

    def do_intersect(self, words):
        """Do a raw intersect between tokens (default limit 100).
        INTERSECT rue des lilas [LIMIT 100]"""
        start = time.time()
        limit = 100
        if 'LIMIT' in words:
            words, limit = words.split('LIMIT')
            limit = int(limit)
        tokens = [token_key(w) for w in preprocess_query(words)]
        DB.zinterstore(words, tokens)
        results = DB.zrevrange(words, 0, limit, withscores=True)
        DB.delete(words)
        for id_, score in results:
            r = SearchResult(id_)
            print(white(r), blue(r.id), cyan(score))
        duration = round((time.time() - start) * 1000, 1)
        print(magenta("({} in {} ms)".format(len(results), duration)))

    def prompt(self):
        command = input("> ")
        return command

    def handle_command(self, command_line):
        if not command_line:
            return
        if not command_line.startswith(tuple(self.COMMANDS.keys())):
            action = 'SEARCH'
            arg = command_line
        elif command_line.count(' '):
            action, arg = command_line.split(' ', 1)
        else:
            action = command_line
            arg = None
        fx_name = 'do_{}'.format(action.lower())
        if hasattr(self, fx_name):
            return getattr(self, fx_name)(arg)
        else:
            print(red('No command for {}'.format(command_line)))

    def __call__(self):
        self.do_help()

        while 1:
            try:
                command = self.prompt()
                self.handle_command(command)
            except (KeyboardInterrupt, EOFError):
                print(red("\nExiting, bye!"))
                break
            print(yellow('-' * 80))
