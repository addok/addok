import atexit
import cmd
import json
import logging
import re
import time
import os

import geohash

from . import hooks
from .config import config
from .core import Result, Search, compute_geohash_key, reverse
from .db import DB
from .ds import get_document
from .helpers import (
    blue,
    cyan,
    green,
    haversine_distance,
    keys,
    km_to_score,
    magenta,
    red,
    scripts,
    white,
    yellow,
)
from .helpers.index import token_frequency
from .helpers.search import preprocess_query
from .helpers.text import compare_str

try:
    import gnureadline as readline  # For OSX.
except ImportError:
    import readline  # Normal way.


class Cmd(cmd.Cmd):

    intro = (
        white("\nWelcome to the Addok shell o/\n")
        + magenta("Type HELP or ? to list commands.\n")
        + magenta("Type QUIT or ctrl-C or ctrl-D to quit.\n")
    )
    prompt = "> "
    HISTORY_FILE = ".addok_shell_history"

    def __init__(self):
        self._init_history_file()
        super().__init__()
        self.do_HELP = self.do_help

    def _init_history_file(self):
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(self.history_file)
            except FileNotFoundError:
                pass
            atexit.register(self.save_history)

    def save_history(self):
        try:
            readline.write_history_file(self.history_file)
        except FileNotFoundError:
            print(
                red("Unable to write history file to " "{}.".format(self.history_file))
            )

    @property
    def history_file(self):
        return os.path.join(os.path.expanduser("~"), self.HISTORY_FILE)

    def error(self, message):
        print(red(message))

    def default(self, line):
        if line == "EOF":
            return self.quit()
        return self.do_SEARCH(line)

    def quit(self):
        print(red("Bye!"))
        return True

    def loop(self, *args):
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            return self.quit()

    def completenames(self, text, *ignored):
        return super().completenames(text.upper(), *ignored)

    def get_names(self):
        special = ["do_help", "do_QUIT"]
        return [n for n in super().get_names() if n not in special]

    def postcmd(self, stop, line):
        if line != "EOF":
            print(yellow("-" * 80))
        return super().postcmd(stop, line)

    @classmethod
    def register_command(cls, command, name=None, doc=None):
        if name is None:
            name = command.__name__
        if doc is None:
            doc = command.__doc__
        if name.startswith("do_"):
            name = name[3:]
        name = "do_" + name.upper()
        setattr(cls, name, command)
        attr = getattr(cls, name)
        attr.__doc__ = doc

    @classmethod
    def register_commands(cls, *commands, **named):
        for command in commands:
            cls.register_command(command)
        for name, command in named.items():
            cls.register_command(command, name)

    def do_help(self, command):
        """Display this help message."""
        if command:
            doc = getattr(self, "do_" + command).__doc__
            print(cyan(doc.replace(" " * 8, "")))
        else:
            print(magenta("Available commands:"))
            print(magenta('Type "HELP <command>" to get more info.'))
            names = self.get_names()
            names.sort()
            for name in names:
                if name[:3] != "do_":
                    continue
                doc = getattr(self, name).__doc__
                doc = doc.split("\n")[0]
                print(
                    "{} {}".format(
                        yellow(name[3:]),
                        cyan(doc.replace(" " * 8, " ").replace("\n", "")),
                    )
                )

    @staticmethod
    def _match_option(key, string):
        matchs = re.findall("{}[= ][^ ]*".format(key), string)
        option = None
        if matchs:
            option = matchs[0]
            string = string.replace(option, "")
            option = option.replace(key, "")
        return string.strip(), option.strip(" =") if option else option

    def _search(self, query, verbose=False, bucket=False, count=1):
        limit = 10
        autocomplete = True
        lat = None
        lon = None
        filters = {}
        if "AUTOCOMPLETE" in query:
            query, autocomplete = self._match_option("AUTOCOMPLETE", query)
            autocomplete = bool(int(autocomplete))
        if "LIMIT" in query:
            query, limit = self._match_option("LIMIT", query)
            limit = int(limit)
        if "CENTER" in query:
            query, center = self._match_option("CENTER", query)
            lat, lon = center.split()
            lat = float(lat)
            lon = float(lon)
        for name in config.FILTERS:
            name = name.upper()
            if name in query:
                query, value = self._match_option(name, query)
                if value:
                    filters[name.lower()] = value.strip()
        helper = Search(limit=limit, verbose=verbose, autocomplete=autocomplete)
        start = time.time()
        for i in range(0, count):
            results = helper(query, lat=lat, lon=lon, **filters)
        if bucket:  # Means we want all the bucket
            results = helper._sorted_bucket
        duration = round((time.time() - start) * 1000 / count, 1)
        if verbose:
            helper.report()

        def format_scores(result):
            if verbose or bucket:
                return ", ".join(
                    "{}: {}/{}".format(k, round(v[0], 4), v[1])
                    for k, v in result._scores.items()
                )
            else:
                return result.score

        for result in results:
            print(
                "{} ({} | {})".format(
                    white(result), blue(result._id), blue(format_scores(result))
                )
            )
        formatter = red if duration > 50 else green
        print(
            "{} — {} — {}".format(
                formatter("{} ms".format(duration)),
                magenta("{} run(s)".format(count)),
                cyan("{} results".format(len(results))),
            )
        )

    def do_QUIT(self, *args):
        """Quit this shell. Also ctrl-C or Ctrl-D."""
        return self.quit()

    def do_SEARCH(self, query):
        """Issue a search (default command, can be omitted):
        SEARCH rue des Lilas [CENTER lat lon] [LIMIT 10] [AUTOCOMPLETE 0] [FILTER VALUE…]"""  # noqa
        self._search(query)

    def do_EXPLAIN(self, query):
        """Issue a search with debug info:
        EXPLAIN rue des Lilas"""
        self._search(query, verbose=True)

    def do_BUCKET(self, query):
        """Issue a search and return all the collected bucket, not only up to
        limit elements:
        BUCKET rue des Lilas"""
        self._search(query, bucket=True)

    def do_BENCH(self, query):
        """Run a search many times to benchmark it.
        BENCH [100] rue des Lilas"""
        try:
            count = int(re.match(r"^(\d+).*", query).group(1))
        except AttributeError:
            count = 100
        self._search(query, count=count)

    def do_INTERSECT(self, words):
        """Do a raw intersect between tokens (default limit 100).
        INTERSECT rue des lilas [LIMIT 100]"""
        start = time.time()
        limit = 100
        if "LIMIT" in words:
            words, limit = words.split("LIMIT")
            limit = int(limit)
        tokens = [keys.token_key(w) for w in preprocess_query(words)]
        DB.zinterstore(words, tokens)
        results = DB.zrevrange(words, 0, limit, withscores=True)
        DB.delete(words)
        for id_, score in results:
            r = Result(id_)
            print("{} {} {}".format(white(r), blue(r._id), cyan(score)))
        duration = round((time.time() - start) * 1000, 1)
        print(magenta("({} in {} ms)".format(len(results), duration)))

    def do_DBINFO(self, *args):
        """Print some useful infos from Redis DB."""
        info = DB.info()
        keys = [
            "keyspace_misses",
            "keyspace_hits",
            "used_memory_human",
            "total_commands_processed",
            "total_connections_received",
            "connected_clients",
        ]
        for key in keys:
            print("{}: {}".format(white(key), blue(info[key])))
        nb_of_redis_db = int(DB.config_get("databases")["databases"])
        for db_index in range(nb_of_redis_db - 1):
            db_name = "db{}".format(db_index)
            if db_name in info:
                label = white("nb keys (db {})".format(db_index))
                print("{}: {}".format(label, blue(info[db_name]["keys"])))

    def do_DBKEY(self, key):
        """Print raw content of a DB key.
        DBKEY g|u09tyzfe"""
        type_ = DB.type(key).decode()
        if type_ == "set":
            out = DB.smembers(key)
        elif type_ == "string":
            out = DB.get(key)
        else:
            out = "Unsupported type {}".format(type_)
        print("type:", magenta(type_))
        print("value:", white(out))

    def do_GEODISTANCE(self, s):
        """Compute geodistance from a result to a point.
        GEODISTANCE 772210180J 48.1234 2.9876"""
        try:
            _id, lat, lon = s.split()
        except:
            return self.error("Malformed query. Use: ID lat lon")
        try:
            result = Result(keys.document_key(_id))
        except ValueError as e:
            return self.error(e)
        center = (float(lat), float(lon))
        km = haversine_distance((float(result.lat), float(result.lon)), center)
        score = km_to_score(km)
        print("km: {} | score: {}".format(white(km), blue(score)))

    def do_GEOHASHTOGEOJSON(self, geoh):
        """Build GeoJSON corresponding to geohash given as parameter.
        GEOHASHTOGEOJSON u09vej04 [NEIGHBORS 0|1|2]"""
        geoh, with_neighbors = self._match_option("NEIGHBORS", geoh)
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
                    if other["n"] > bbox["n"]:
                        bbox["n"] = other["n"]
                    if other["s"] < bbox["s"]:
                        bbox["s"] = other["s"]
                    if other["e"] > bbox["e"]:
                        bbox["e"] = other["e"]
                    if other["w"] < bbox["w"]:
                        bbox["w"] = other["w"]

        if with_neighbors > 0:
            expand(bbox, geoh, 0)

        geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [bbox["w"], bbox["n"]],
                    [bbox["e"], bbox["n"]],
                    [bbox["e"], bbox["s"]],
                    [bbox["w"], bbox["s"]],
                    [bbox["w"], bbox["n"]],
                ]
            ],
        }
        print(white(json.dumps(geojson)))

    def do_GEOHASH(self, latlon):
        """Compute a geohash from latitude and longitude.
        GEOHASH 48.1234 2.9876"""
        try:
            lat, lon = map(float, latlon.split())
        except ValueError:
            print(red("Invalid lat and lon {}".format(latlon)))
        else:
            print(white(geohash.encode(lat, lon, config.GEOHASH_PRECISION)))

    def do_GEOHASHMEMBERS(self, geoh):
        """Return members of a geohash and its neighbors.
        GEOHASHMEMBERS u09vej04 [NEIGHBORS 0]"""
        geoh, with_neighbors = self._match_option("NEIGHBORS", geoh)
        key = compute_geohash_key(geoh, with_neighbors != "0")
        if key:
            for id_ in DB.smembers(key):
                r = Result(id_)
                print("{} {}".format(white(r), blue(r._id)))

    def do_GET(self, _id):
        """Get document from index with its id.
        GET 772210180J"""
        doc = doc_by_id(_id)
        if not doc:
            return self.error('id "{}" not found'.format(_id))
        for key, value in doc.items():
            if key == config.HOUSENUMBERS_FIELD:
                continue
            print("{} {}".format(white(key), magenta(value)))
        if doc.get("housenumbers"):

            def sorter(v):
                try:
                    return int(re.match(r"^\d+", v["raw"]).group())
                except AttributeError:
                    return -1

            housenumbers = sorted(doc["housenumbers"].values(), key=sorter)
            print(
                white("housenumbers"),
                magenta(", ".join(v["raw"] for v in housenumbers)),
            )

    def do_FREQUENCY(self, word):
        """Return word frequency in index.
        FREQUENCY lilas"""
        print(white(word_frequency(word)))

    def _print_field_index_details(self, field, _id):
        for token in indexed_string(field):
            print(
                white(token),
                blue(DB.zscore(keys.token_key(token), keys.document_key(_id))),
                blue(DB.zrevrank(keys.token_key(token), keys.document_key(_id))),
            )

    def do_INDEX(self, _id):
        """Get index details for a document by its id.
        INDEX 772210180J"""
        doc = doc_by_id(_id)
        if not doc:
            return self.error('id "{}" not found'.format(_id))
        for field in config.FIELDS:
            key = field["key"]
            if key in doc:
                self._print_field_index_details(doc[key], _id)

    def do_BESTSCORE(self, word):
        """Return document linked to word with higher score.
        BESTSCORE lilas"""
        key = keys.token_key(indexed_string(word)[0])
        for _id, score in DB.zrevrange(key, 0, 20, withscores=True):
            result = Result(_id)
            print(white(result), blue(score), green(result._id))

    def do_REVERSE(self, latlon):
        """Do a reverse search. Args: lat lon.
        REVERSE 48.1234 2.9876"""
        lat, lon = latlon.split()
        for r in reverse(float(lat), float(lon)):
            print(
                "{} ({} | {} km | {})".format(
                    white(r), blue(r.score), blue(r.distance), blue(r._id)
                )
            )

    def do_TOKENIZE(self, string):
        """Inspect how a string is tokenized before being indexed.
        TOKENIZE Rue des Lilas"""
        print(white(" ".join(indexed_string(string))))

    def do_STRDISTANCE(self, s):
        """Print the distance score between two strings. Use | as separator.
        STRDISTANCE rue des lilas|porte des lilas"""
        s = s.split("|")
        if not len(s) == 2:
            print(red("Malformed string. Use | between the two strings."))
            return
        one, two = s
        print(white(compare_str(one, two)))

    def do_CONFIG(self, name):
        """Inspect loaded Addok config. Output all config without argument.
        CONFIG [CONFIG_KEY]"""
        if not name:
            for name in self.complete_CONFIG():
                self.do_CONFIG(name)
            return
        value = getattr(config, name.upper(), "Not found.")
        print(blue(name), white(format_config(value)))

    def complete_CONFIG(self, text=None, *ignored):
        text = text or ""
        return [a for a in config.keys() if a.startswith(text) and a.isupper()]

    def do_SCRIPT(self, args):
        """Run a Lua script. Takes the raw Redis arguments.
        SCRIPT script_name number_of_keys key1 key2… arg1 arg2
        """
        try:
            name, keys_count, *args = args.split()
        except ValueError:
            print(red("Not enough arguments"))
            return
        try:
            keys_count = int(keys_count)
        except ValueError:
            print(red("You must pass the number of keys as first argument"))
            self.do_HELP("SCRIPT")
            return
        keys = args[:keys_count]
        args = args[keys_count:]
        try:
            output = getattr(scripts, name)(keys=keys, args=args)
        except AttributeError:
            print(red("No script named {}".format(name)))
            return
        except DB.Error as e:
            print(red(e))
            return
        if not isinstance(output, list):
            # Script may return just an integer.
            output = [output]
        for line in output:
            print(white(line))


def format_config(value):
    out = ""
    if isinstance(value, (list, tuple)):
        for item in value:
            out += format_config(item)
    elif type(value).__name__ == "function":
        out = "\n{}.{}".format(str(value.__module__), value.__name__)
    else:
        out = "\n{}".format(value)
    return out


def invoke(args=None):
    cmd = Cmd()
    hooks.register_shell_command(cmd)
    cmd.loop()


def pyinvoke(args=None):
    try:
        from IPython import start_ipython
    except ImportError:
        print(red('Import is not installed. Type "pip install ipython"'))
    else:
        start_ipython(
            argv=[], user_ns={"DB": DB, "config": config, "get_document": get_document}
        )


def register_command(subparsers):
    parser = subparsers.add_parser("shell", help="Run a shell to inspect Addok")
    parser.set_defaults(func=invoke)
    parser = subparsers.add_parser(
        "pyshell", help="Run a python shell with Addok config"
    )
    parser.set_defaults(func=pyinvoke)


def doc_by_id(_id):
    return get_document(keys.document_key(_id).encode())


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
