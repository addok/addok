#!/usr/bin/env python

import argparse


def main():
    main_parser = argparse.ArgumentParser(description='Addok command line.')
    subparsers = main_parser.add_subparsers(title='Available commands',
                                            metavar='')

    # if args['--config']:
    #     os.environ['ADDOK_CONFIG_MODULE'] = args['--config']

    from addok import config
    config.load_plugins(config)
    config.pm.hook.addok_register_command(subparsers=subparsers)
    args = main_parser.parse_args()
    if getattr(args, 'func', None):
        args.func(args)
    else:
        main_parser.print_help()

    # elif args['ngrams']:
    #     create_edge_ngrams()

if __name__ == '__main__':
    main()
