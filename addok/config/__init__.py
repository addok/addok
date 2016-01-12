import imp
import importlib
import pluggy
import os
import sys

from .default import *  # noqa
from addok import hooks


def extend_from_file(path):
    d = imp.new_module('config')
    d.__file__ = path
    try:
        with open(path) as config_file:
            exec(compile(config_file.read(), path, 'exec'), d.__dict__)
    except IOError as e:
        from addok.helpers import red
        print(red('Unable to import {} from '
                  'ADDOK_CONFIG_MODULE'.format(path)))
        sys.exit(e)
    else:
        print('Loaded local config from', path)
        extend_from_object(d)


def extend_from_object(d):
    for key in dir(d):
        if key.isupper():
            globals()[key] = getattr(d, key)


HOUSENUMBERS_FIELD = None
NAME_FIELD = None


pm = pluggy.PluginManager('addok')
pm.add_hookspecs(hooks)


def consolidate():
    global HOUSENUMBERS_FIELD
    global NAME_FIELD
    FIELDS.extend(EXTRA_FIELDS)
    for field in FIELDS:
        key = field['key']
        if field.get('type') == 'housenumbers' or key == 'housenumbers':
            HOUSENUMBERS_FIELD = key
            field['type'] = 'housenumbers'
        elif field.get('type') == 'name' or key == 'name':
            NAME_FIELD = key
            field['type'] = 'name'
    resolve_paths()


def resolve_path(name):
    from addok.helpers import import_by_path
    attr = globals()[name]
    for idx, path in enumerate(attr):
        attr[idx] = import_by_path(path)


def resolve_paths():
    names = [
        'QUERY_PROCESSORS', 'RESULTS_COLLECTORS', 'SEARCH_RESULT_PROCESSORS',
        'REVERSE_RESULT_PROCESSORS', 'PROCESSORS', 'INDEXERS', 'DEINDEXERS',
        'BATCH_PROCESSORS'
    ]
    for name in names:
        resolve_path(name)


def load(config, discover=True):
    # 1. Try to load local setting from a local path (allow to include or
    # exclude plugins from local config).
    localpath = os.environ.get('ADDOK_CONFIG_MODULE')
    if localpath:
        extend_from_file(localpath)

    # 2. Load plugins.
    load_core_plugins()
    if discover:
        pm.load_setuptools_entrypoints("addok.ext")
    names = [name for name, module in pm.list_name_plugin()]
    print('Addok loaded plugins: {}'.format(', '.join(names)))

    # 3. Allow plugins to set default config.
    pm.hook.addok_preconfigure(config=config)

    # 4. Now reload local config if any, to override any plugin default.
    if localpath:
        extend_from_file(localpath)

    # 5. Now let plugin configure themselves.
    pm.hook.addok_configure(config=config)

    # 5. Finally, consolidate values.
    consolidate()


def load_core_plugins():
    for path in PLUGINS:
        plugin = importlib.import_module(path)
        pm.register(plugin)
