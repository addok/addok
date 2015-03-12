import os
import re

from importlib import import_module

from .default import *  # noqa

try:
    user_settings = import_module(os.environ["ADDOK_CONFIG_MODULE"])
except ImportError:
    print('Unable to import', os.environ["ADDOK_CONFIG_MODULE"])
except KeyError:
    pass
else:
    # Override with user ones
    for attr in dir(user_settings):
        if re.search('^[A-Z]', attr):
            globals()[attr] = getattr(user_settings, attr)
finally:
    HOUSENUMBERS_FIELD = None
    NAME_FIELD = None
    for field in FIELDS:
        key = field['key']
        if field.get('type') == 'housenumbers' or key == 'housenumbers':
            HOUSENUMBERS_FIELD = key
        elif field.get('type') == 'name' or key == 'name':
            NAME_FIELD = key
