import os
import importlib
import types
import sys
import warnings


from importlib.metadata import version as get_version, PackageNotFoundError

from addok import hooks, VERSION
from . import default


class Config(dict):

    TESTING = False

    def __init__(self):
        self._post_load_func = []
        self.loaded = False
        self.plugins = [
            "addok.shell",
            "addok.http.base",
            "addok.batch",
            "addok.pairs",
            "addok.fuzzy",
            "addok.autocomplete",
        ]
        super().__init__()
        self.extend_from_object(default)

    def load(self):
        if self.loaded:
            return
        self.loaded = True
        self.load_core_plugins()
        if not Config.TESTING:
            # We don't want to autoload installed plugin during tests.
            hooks.load()  # pragma: no cover
        hooks.preconfigure(self)
        self.load_local()
        self.load_from_env()
        hooks.configure(self)
        self.resolve()
        self.post_process()
        plugins = []
        for name, plugin in hooks.plugins.items():  # pragma: no cover
            if name.startswith("addok."):
                version = VERSION  # Core plugin.
            else:
                try:
                    version = get_version(plugin.__package__)
                except PackageNotFoundError:
                    version = "?"
            plugins.append("{}=={}".format(name, version))
        print("Loaded plugins:\n{}".format(", ".join(plugins)))

    def on_load(self, func):
        self._post_load_func.append(func)
        return func

    def extend_from_object(self, obj):
        for key in dir(obj):
            if key.isupper():
                self[key] = getattr(obj, key)

    def load_core_plugins(self):
        for path in self.plugins:
            plugin = importlib.import_module(path)
            hooks.register(plugin)

    def load_local(self):
        path = os.environ.get("ADDOK_CONFIG_MODULE") or os.path.join(
            "/etc", "addok", "addok.conf"
        )
        if not os.path.exists(path):
            print('No local config file found in "{}".'.format(path))
            return

        d = types.ModuleType("config")
        d.__file__ = path
        try:
            with open(path) as config_file:
                exec(compile(config_file.read(), path, "exec"), d.__dict__)
        except (IOError, SyntaxError) as e:
            from addok.helpers import red

            print(red("Unable to import {} from " "ADDOK_CONFIG_MODULE".format(path)))
            sys.exit(e)
        else:
            print("Loaded local config from", path)
            self.extend_from_object(d)

    def load_from_env(self):
        for key, value in self.items():
            if key.isupper():
                env_key = "ADDOK_" + key
                typ = type(value)
                if typ in (list, tuple, set):
                    real_type, typ = typ, lambda x: real_type(x.split(","))
                if env_key in os.environ:
                    self[key] = typ(os.environ[env_key])

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value

    def post_process(self):
        # Retrocompat
        if self.SYNONYMS_PATH:
            warnings.warn(
                "SYNONYMS_PATH is deprecated, use SYNONYMS_PATHS instead",
                DeprecationWarning,
            )
            self.SYNONYMS_PATHS.append(self.SYNONYMS_PATH)
        self.FIELDS.extend(self.EXTRA_FIELDS)
        for field in self.FIELDS:
            key = field["key"]
            if field.get("type") == "housenumbers" or key == "housenumbers":
                self.HOUSENUMBERS_FIELD = key
                field["type"] = "housenumbers"
            elif field.get("type") == "name" or key == "name":
                self.NAME_FIELD = key
                field["type"] = "name"
            elif field.get("type") == "id":
                self.ID_FIELD = key
        for func in self._post_load_func:
            func()

    def resolve(self):
        for key in list(self.keys()):
            if key.endswith("_PYPATHS"):
                self.resolve_paths(key)
            elif key.endswith("_PYPATH"):
                self.resolve_path(key)

    def resolve_path(self, key):
        from addok.helpers import import_by_path

        self[key[: -len("_PYPATH")]] = import_by_path(self[key])

    def resolve_paths(self, key):
        from addok.helpers import import_by_path

        self[key[: -len("_PYPATHS")]] = [import_by_path(path) for path in self[key]]


config = Config()
