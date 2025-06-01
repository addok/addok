# Installing Addok

## Dependencies

- Redis >= 5.0 <= 7.4
- python >= 3.9 <= 3.13

## Install using a virtualenv

1. Install dependencies:

        sudo apt-get install redis-server python3 python3-dev python-pip python-virtualenv

1. create a virtualenv:

        virtualenv addok --python=/usr/bin/python3

1. active virtualenv:

        source addok/bin/activate

1. install python packages:

        pip install addok

## What to do next?
Now you certainly want to [configure Addok](config.md), install
[plugins](plugins.md) or directly [import data](import.md).

See also the full [installation tutorial](tutorial.md).
