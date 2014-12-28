#!/usr/bin/env python
"""
Addok: search engine for address. Only address.
Usage:
    run.py serve [--port=<number>] [--host=<string>] [options]
    run.py shell

Examples:
    python run.py serve --port 5432 --debug
    python run.py shell

Options:
    -h --help           print this message and exit
    --port=<number>     optionnaly pass a server port [default: 7878]
    --host=<string>     optionnaly pass a server port [default: 127.0.0.1]
    --debug             optionnaly run in debug mode
"""

from docopt import docopt

from addok.server import app
from addok.debug import Cli

if __name__ == '__main__':

    args = docopt(__doc__, version='Piati 0.1')

    if args['serve']:
        from werkzeug.serving import run_simple
        run_simple(args['--host'], int(args['--port']), app,
                   use_debugger=True, use_reloader=True)
    elif args['shell']:
        cli = Cli()
        cli()
