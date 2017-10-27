# Installing Addok

## Dependencies

- Redis
- python >= 3.4

## Install using a virtualenv

1. Install dependencies:

        sudo apt-get install redis-server python3.5 python3.5-dev python-pip python-virtualenv

1. create a virtualenv:

        virtualenv addok --python=/usr/bin/python3.5

1. active virtualenv:

        source addok/bin/activate

1. install python packages:

        pip install addok

### Using Cython (optional)

For a performance boost, you can use Cython:

```bash
pip install cython
pip install --no-binary :all: addok
```

Note: this is not recommended for development.

Note: `--no-binary` option is only available for recent `pip` versions,
to make sure you're running the latest, run `pip install -U pip`.

## What to do next?
Now you certainly want to [configure Addok](config.md), install
[plugins](plugins.md) or directly [import data](import.md).

See also the full [installation tutorial](tutorial.md).
