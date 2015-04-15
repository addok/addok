#!/usr/bin/env python
"""
Addok: search engine for address. Only address.
Usage:
    addok serve [--port=<number>] [--host=<string>] [options]
    addok shell
    addok batch [<filepath>...] [options]
    addok ngrams

Examples:
    addok serve --port 5432 --debug
    addok shell
    addok batch path/to/bano-full.csv
    addok batch < cat path/to/bano-full.csv
    addok batch --dbuser myname --dbname mydb
    addok batch ngrams

Options:
    -h --help           print this message and exit
    --port=<number>     optionnaly pass a server port [default: 7878]
    --host=<string>     optionnaly pass a server port [default: 127.0.0.1]
    --debug             optionnaly run in debug mode
    --dbname=<string>   override dbname
    --dbuser=<string>   override dbuser
    --dbhost=<string>   override dbhost
    --dbport=<string>   override dbport
    --limit=<number>    add an optional limit
"""

import sys

from docopt import docopt

from addok import config
from addok.debug import Cli
from addok.server import app
from addok import batch
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
        if args['<filepath>']:
            for path in args['<filepath>']:
                batch.process_file(path)
        elif not sys.stdin.isatty():  # Any better way to check for stdin?
            batch.process_stdin(sys.stdin)
        else:
            if args['--dbname']:
                config.PSQL['dbname'] = args['--dbname']
            if args['--dbuser']:
                config.PSQL['user'] = args['--dbuser']
            if args['--dbhost']:
                config.PSQL['host'] = args['--dbhost']
            if args['--dbport']:
                config.PSQL['port'] = args['--dbport']
            if args['--limit']:
                config.PSQL_LIMIT = args['--limit']
            batch.process_psql()
    elif args['ngrams']:
        create_edge_ngrams()

if __name__ == '__main__':
    main()
