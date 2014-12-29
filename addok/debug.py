import logging
import readline  # Enable history in cli.

from addok.core import DB, preprocess, search, document_key, token_frequency


def doc_by_id(_id):
    return DB.hgetall(document_key(_id))


def indexed_string(s):
    return list(preprocess(s))


def word_frequency(word):
    token = list(preprocess(word))[0]
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

    COMMANDS = ('SEARCH', 'DOC', 'TOKENIZE', 'DEBUG', 'FREQUENCY')

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
        for result in search(query):
            print('{} ({} | {})'.format(white(result), blue(result.score),
                                        blue(result.id)))

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
