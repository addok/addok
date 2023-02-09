# Plugins

## Installing a plugin

Each plugin may have its own installation process, but usually it takes two steps:

- install a python package, for example: `pip install addok-france`
- adapt your local configuration to the plugin needs

Check each plugin home page to have specific documentation.


## Known plugins

- [addok-france](https://github.com/addok/addok-france): add specificities of France addresses to
  addok (for example address parsing, address labelling for score computing, etc.)
- [addok-fr](https://github.com/addok/addok-fr): French dedicated plugin, for example for phonemisation
  (better typo tolerance).
- [addok-csv](https://github.com/addok/addok-csv): add a CSV endpoint to your Addok server (for batch
  geocoding of CSV files)
- [addok-psql](https://github.com/addok/addok-psql): import from PostgreSQL database into Addok.
- [addok-trigrams](https://github.com/addok/addok-trigrams): alternative index algorithm based on trigrams.
- [addok-sqlite-store](https://github.com/addok/addok-sqlite-store): store documents into SQLite.

## Writing a plugin

As usual, best way to learn is to look at the code: look at the other plugins for inspiration.

### Anatomy of a plugin

An Addok plugin is simply a python module:

- it must be installed in the PYTHONPATH for addok to be able to import it
- it should have the `addok.ext` entry point in case it needs to use the API
  end points

### addok.ext entry point

Note: this is only needed if you want to use hooks within your plugin.
For example, if the plugin only deals with configuration
(adding a PROCESSOR, changing the document store, etc), there is no need
for that.

Add this to your `setup.py`:

```python
setup(
    name='addok-mysuperplugin',
    …,
    entry_points={'addok.ext': ['mysuperplugin=relative.path.to.plugin']},
)
```

Say for example that the plugin structure is:

```
mysuperplugin/
    setup.py
    README.md
    mysuperplugin/
        __init__.py
        utils.py
        hooks.py
```

If you put the hooks in `hooks.py`, then your entrypoint should be:

```python
    entry_points={'addok.ext': ['mysuperplugin=mysuperplugin.hooks']},
```

### Plugins hooks

If you have added an entry point to your plugin, addok will look for some hooks
and call them if you have defined them.

Important: those hooks must be in the module defined in the entrypoint.


#### preconfigure(config)

Allow to modify config object before user local config is loaded (for example
to set defaults overridable by the plugin user in their local config).


#### configure(config)

Allow to modify config object after user local config has been loaded.


#### register_http_endpoint(api)

Add new endpoints to the HTTP API. It uses [Falcon](http://falcon.readthedocs.io/)
so each [view](http://falcon.readthedocs.io/en/stable/api/request_and_response.html)
must comply to Falcon's contract:

```python
class MyFalconView:

    def on_get(self, req, resp, myparameter):
        resp.body = do_something(myparameter)
        resp.status = 200
        resp.content_type = 'text/html'

def register_http_endpoint(api):
    api.add_route('/path/{myparameter}', MyFalconView())
```

#### register_http_middleware(middlewares)

Add new middlewares to the HTTP API. It uses [Falcon](http://falcon.readthedocs.io/)
so each [middleware](http://falcon.readthedocs.io/en/stable/api/middleware.html)
must comply to Falcon's contract:

```python
class MyFalconMiddleware:

    def process_request(self, req, resp):
        ...

    def process_resource(self, req, resp, resource, params):
        ...

    def process_response(self, req, resp, resource, req_succeeded):
        ...

def register_http_middleware(middlewares):
    middlewares.append(MyFalconMiddleware())
```

#### register_command(subparsers):

Register command for Addok CLI.

```python
def my_callable(*args):
    # `args` are parsed from command-line.
    do_whatever_with(args)


def register_command(subparsers):
    parser = subparsers.add_parser('mycommand', help='Documentation.')
    parser.set_defaults(func=my_callable)
```

#### register_shell_command(cmd):

Register command for Addok shell. The command must start with `do_` to
be registered as a command and the command must be uppercase.

The first line of the command docstring will be displayed when using `HELP`
in the shell and the whole docstring will be displayed when using
`HELP WHATEVER`.

```python
def do_WHATEVER(cmd, remaining_string):
    """Allow to use the `WHATEVER` command within the shell."""
    # `cmd` is the Cmd instance.
    # `remaining_string` is everything typed by the user after the
    # command name.

def register_shell_command(cmd):
    cmd.register_command(do_WHATEVER)
```


## Writing a store plugin

Document stores are particular plugins given they must follow a strict API.
Again, check out existing stores (especially
[SQLite](https://github.com/addok/addok-sqlite-store)) for inspiration.

It has to be a class with 4 methods:

### fetch(self, *keys)

Must yield a key and the associated document for each passed keys.

### upsert(self, *docs)

Must up(date or ins)ert documents passed as parameters.

### remove(self, *keys)

Must remove documents related to passed keys.

#### flushdb(self)

Must remove all documents from the database.
Only in use by the `reset` command.

Once your store plugin is compliant, do not forget to update the
[DOCUMENT_STORE_PYPATH](config.md) setting to test it.
