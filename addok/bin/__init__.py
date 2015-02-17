#!/usr/bin/env python
"""
Addok: search engine for address. Only address.
Usage:
    run.py serve [--port=<number>] [--host=<string>] [options]
    run.py shell
    run.py import [<filepath>...]
    run.py ngrams

Examples:
    python run.py serve --port 5432 --debug
    python run.py shell
    python import path/to/bano-full.csv

Options:
    -h --help           print this message and exit
    --port=<number>     optionnaly pass a server port [default: 7878]
    --host=<string>     optionnaly pass a server port [default: 127.0.0.1]
    --debug             optionnaly run in debug mode
"""

import sys

from docopt import docopt

from addok.debug import Cli
from addok.server import app
from addok.import_utils import (import_from_stream_json, create_edge_ngrams,
                                import_from_stream_json_file)


def main():
    args = docopt(__doc__, version='Addok 0.1')

    if args['serve']:
        from werkzeug.serving import run_simple
        run_simple(args['--host'], int(args['--port']), app,
                   use_debugger=True, use_reloader=True)
    elif args['shell']:
        cli = Cli()
        cli()
    elif args['import']:
        for path in args['<filepath>']:
            import_from_stream_json_file(path)
        if not sys.stdin.isatty():  # Any best way to check for data in stdin?
            print('Import from stdin')
            import_from_stream_json(sys.stdin)
    elif args['ngrams']:
        create_edge_ngrams()

if __name__ == '__main__':
    main()
