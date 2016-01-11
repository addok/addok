import imp
import importlib
import pluggy
import os
import sys

from .default import *  # noqa
from addok import hooks

# Try to load local setting from a local path.
localpath = os.environ.get('ADDOK_CONFIG_MODULE')
if localpath:
    d = imp.new_module('config')
    d.__file__ = localpath
    try:
        with open(localpath) as config_file:
            exec(compile(config_file.read(), localpath, 'exec'), d.__dict__)
    except IOError as e:
        from addok.utils import red
        print(red('Unable to import {} from '
                  'ADDOK_CONFIG_MODULE'.format(localpath)))
        sys.exit(1)
    else:
        print('Loaded local config from', localpath)
        for key in dir(d):
            if key.isupper():
                globals()[key] = getattr(d, key)

HOUSENUMBERS_FIELD = None
NAME_FIELD = None
FIELDS.extend(EXTRA_FIELDS)
for field in FIELDS:
    key = field['key']
    if field.get('type') == 'housenumbers' or key == 'housenumbers':
        HOUSENUMBERS_FIELD = key
        field['type'] = 'housenumbers'
    elif field.get('type') == 'name' or key == 'name':
        NAME_FIELD = key
        field['type'] = 'name'


pm = pluggy.PluginManager('addok')
pm.add_hookspecs(hooks)


def load_plugins(config, load_external=True):
    load_core_plugins()
    if load_external:
        load_external_plugins()
    names = [name for name, module in pm.list_name_plugin()]
    print('Addok loaded plugins: {}'.format(', '.join(names)))
    pm.hook.addok_configure(config=config)
    load()


def load_core_plugins():
    for path in PLUGINS:
        plugin = importlib.import_module(path)
        pm.register(plugin)


def load_external_plugins():
    pm.load_setuptools_entrypoints("addok.ext")


def on_load(func):
    ON_LOAD.append(func)
ON_LOAD = []


def load():
    for func in ON_LOAD:
        func()
