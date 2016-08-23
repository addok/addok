#!/usr/bin/env python

import argparse
import os


def main():

    main_parser = argparse.ArgumentParser(description='Addok command line.')
    main_parser.add_argument('--config', help='Local config')
    args, extras = main_parser.parse_known_args()
    if args.config:
        os.environ['ADDOK_CONFIG_MODULE'] = args.config

    subparsers = main_parser.add_subparsers(title='Available commands',
                                            metavar='')

    from addok import config, hooks
    config.load(config)
    hooks.register_command(subparsers)
    args = main_parser.parse_args(args=extras)
    if getattr(args, 'func', None):
        args.func(args)
    else:
        main_parser.print_help()

if __name__ == '__main__':
    main()
