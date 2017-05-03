# Deploy with Fabric

You must use [Fabric](http://www.fabfile.org/) with
[v2 branch](https://github.com/fabric/fabric/tree/v2)
to be able to run it with Python 3.

## Implementation choices

* all commands are idempotent
* custom configuration file should be inspired by `fabfile/france.fabric.yml`
  and must be passed to each command with the `--config` parameter


## One command to rule-them-all

```bash
fab --echo --hosts=root@ip --config=fabfile/your-config.yml bootstrap deploy reload
```

It will install addok, load data from `data_uri` and expose it through
uwsgi/nginx.

## Settings

### `settings`

Custom addok settings file path for your instance.

### `data_uri`

Link to a bziped JSON file to be loaded.

### `domain`

Domain name for your service.

### `plugins` (optional)

List of Python packages to be installed as addok plugins.

### `data` (optional)

Additional data to be loaded as a list of JSON objects.

### `skip_nginx` (optional)

Set to `true` if you want to avoid installing/running nginx.


## Commands

### `system`

Start with that command to update the system, install dependencies and create
approriated user and folders.

### `venv`

Create the virtualenv and update [pip](https://pip.pypa.io/en/stable/).

### `settings`

Load custom settings from your local file referenced as `settings`
in the configuration file.

### `http`

Install configuration for uwsgi and nginx.

### `bootstrap` (meta)

Run commands `system`, `venv`, `settings` and `http`.

### `fetch`

Retrieve the file referenced as `data_uri` in the configuration
file and unbzip it.

### `batch`

Load the previously fetched file plus optional data from the
configuration file.

### `reload` (meta)

Run `fetch`, stop uwsgi, reset addok database(s), run `batch` and restart
services.

### `deploy`

Install addok and all plugins referenced as `plugins` in the
configuration file.

### `restart`

Restart uwsgi and nginx.
