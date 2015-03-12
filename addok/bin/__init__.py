#!/usr/bin/env python
"""
Addok: search engine for address. Only address.
Usage:
    addok serve [--port=<number>] [--host=<string>] [options]
    addok shell
    addok batch (bano [<filepath>...] | nominatim [options])
    addok ngrams

Examples:
    addok serve --port 5432 --debug
    addok shell
    addok batch bano path/to/bano-full.csv
    addok batch bano < cat path/to/bano-full.csv
    addok batch nominatim
    addok batch nominatim --only-address
    addok batch ngrams

Options:
    -h --help           print this message and exit
    --port=<number>     optionnaly pass a server port [default: 7878]
    --host=<string>     optionnaly pass a server port [default: 127.0.0.1]
    --debug             optionnaly run in debug mode
    --only-address      only import addresses (when running Nominatim import)
    --no-address        Do not import addresses (when running Nominatim import)
    --dbname=<string>   override dbname [default: nominatim]
    --user=<string>     override dbname [default: nominatim]
    --limit=<number>    add an optional
"""

import sys

from docopt import docopt

from addok.debug import Cli
from addok.server import app
from addok.batch import bano
from addok.index_utils import create_edge_ngrams


def main():
    args = docopt(__doc__, version='Addok 0.1')

    if args['serve']:
        from werkzeug.serving import run_simple
        run_simple(args['--host'], int(args['--port']), app,
                   use_debugger=True, use_reloader=True)
    elif args['shell']:
        cli = Cli()
        cli()
    elif args['batch']:
        if args['bano']:
            for path in args['<filepath>']:
                bano.process_file(path)
            if not sys.stdin.isatty():  # Any better way to check for stdin?
                bano.process_stdin(sys.stdin)
        elif args['nominatim']:
            # Do not import at load time, because we don't want to have a
            # hard dependency to psycopg2, which is imported on nominatim
            # module.
            from addok.batch import nominatim
            nominatim.import_from_sql(
                dbname=args['--dbname'], user=args['--user'],
                limit=args['--limit'], onlyaddress=args['--only-address'],
                noaddress=args['--no-address']
            )
    elif args['ngrams']:
        create_edge_ngrams()

if __name__ == '__main__':
    main()
