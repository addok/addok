# Installing Addok

## Dependencies

- Redis >= 7.2 <= 8.0
- python >= 3.9 <= 3.14

## Install using a virtualenv

1. Install dependencies:

        sudo apt-get install redis-server python3 python3-dev python3-pip python3-venv

1. Create a virtual environment:

        python3 -m venv addok

1. Activate the virtual environment:

        source addok/bin/activate

1. install python packages:

        pip install addok

    **For production environments**, it's recommended to install the performance optimization extras:

        pip install addok[perf]

    This installs `hiredis`, a fast C parser for Redis that significantly improves performance.

## What to do next?
Now you certainly want to [configure Addok](config.md), install
[plugins](plugins.md) or directly [import data](import.md).

See also the full [installation tutorial](tutorial.md).
