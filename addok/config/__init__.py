import imp
import os
import sys

from .default import *  # noqa

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
