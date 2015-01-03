import logging
import readline
import time

from addok.core import (DB, search, document_key, token_frequency,
                        token_key, Result, Token)
from addok.pipeline import preprocess_query


def doc_by_id(_id):
    return DB.hgetall(document_key(_id))


def indexed_string(s):
    return list(preprocess_query(s))


def word_frequency(word):
    token = list(preprocess_query(word))[0]
    return token_frequency(token)


def set_debug():
    logging.basicConfig(level=logging.DEBUG)


COLORS = {
    'red': '31',
    'green': '32',
    'yellow': '33',
    'blue': '34',
    'magenta': '35',
    'cyan': '36',
    'white': '37',
    'reset': '39'
}


def colorText(s, color):
    # color should be a string from COLORS
    return '\033[%sm%s\033[%sm' % (COLORS[color], s, COLORS['reset'])


def red(s):
    return colorText(s, 'red')


def green(s):
    return colorText(s, 'green')


def yellow(s):
    return colorText(s, 'yellow')


def blue(s):
    return colorText(s, 'blue')


def magenta(s):
    return colorText(s, 'magenta')


def cyan(s):
    return colorText(s, 'cyan')


def white(s):
    return colorText(s, 'white')


class Cli(object):

    COMMANDS = (
        'SEARCH', 'DOC', 'TOKENIZE', 'DEBUG', 'FREQUENCY', 'INDEX',
        'BESTSCORE', 'AUTOCOMPLETE'
    )

    def __init__(self):
        readline.set_completer(self.completer)
        readline.parse_and_bind("tab: complete")

    def completer(self, text, state):
        for cmd in self.COMMANDS:
            if cmd.startswith(text.upper()):
                if not state:
                    return cmd + " "
                else:
                    state -= 1

    def do_search(self, query):
        start = time.time()
        for result in search(query):
            print('{} ({} | {})'.format(white(result), blue(result.score),
                                        blue(result.id)))
        print(magenta("({} seconds)".format(time.time() - start)))

    def do_tokenize(self, string):
        print(white(' '.join(indexed_string(string))))

    def do_help(self, *args):
        print(cyan('Commands:'), yellow(' '.join(self.COMMANDS)))

    def do_debug(self, *args):
        set_debug()

    def do_doc(self, _id):
        print(white(doc_by_id(_id)))

    def do_frequency(self, word):
        print(white(word_frequency(word)))

    def do_autocomplete(self, s):
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
        doc = doc_by_id(_id)
        self._print_field_index_details(doc[b'name'].decode(), _id)
        self._print_field_index_details(doc[b'postcode'].decode(), _id)
        self._print_field_index_details(doc[b'city'].decode(), _id)

    def do_bestscore(self, word):
        key = token_key(indexed_string(word)[0])
        for _id, score in DB.zrevrange(key, 0, 10, withscores=True):
            doc = DB.hgetall(_id)
            result = Result(doc)
            print(white(result), blue(score), blue(result.id))

    def prompt(self):
        command = input("> ")
        return command

    def handle_command(self, command_line):
        if not command_line:
            return
        if not command_line.startswith(self.COMMANDS):
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
