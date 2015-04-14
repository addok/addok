#!/usr/bin/env python
"""
Addok: search engine for address. Only address.
Usage:
    addok serve [--port=<number>] [--host=<string>] [options]
    addok shell
    addok batch [nominatim] [<filepath>...] [options]
    addok ngrams

Examples:
    addok serve --port 5432 --debug
    addok shell
    addok batch path/to/bano-full.csv
    addok batch < cat path/to/bano-full.csv
    addok batch nominatim
    addok batch nominatim --only-address
    addok batch ngrams

Options:
    -h --help           print this message and exit
    --port=<number>     optionnaly pass a server port [default: 7878]
    --host=<string>     optionnaly pass a server port [default: 127.0.0.1]
    --debug             optionnaly run in debug mode
    --dbname=<string>   override dbname [default: nominatim]
    --dbuser=<string>   override dbuser [default: nominatim]
    --dbhost=<string>   override dbhost
    --dbport=<string>   override dbport
    --nominatim-mode    One of full | only-address | no-address
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
        if args['nominatim']:
            if args['--dbname']:
                config.NOMINATIM_CREDENTIALS['dbname'] = args['--dbname']
            if args['--dbuser']:
                config.NOMINATIM_CREDENTIALS['user'] = args['--dbuser']
            if args['--dbhost']:
                config.NOMINATIM_CREDENTIALS['host'] = args['--dbhost']
            if args['--dbport']:
                config.NOMINATIM_CREDENTIALS['port'] = args['--dbport']
            if args['--nominatim-mode']:
                config.NOMINATIM_MODE = args['--nominatim-mode']
            batch.process_nominatim()
        else:
            for path in args['<filepath>']:
                batch.process_file(path)
            if not sys.stdin.isatty():  # Any better way to check for stdin?
                batch.process_stdin(sys.stdin)
    elif args['ngrams']:
        create_edge_ngrams()

if __name__ == '__main__':
    main()
