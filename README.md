# Addok

Search engine for address. Only address.


# Dependencies

- Redis
- Python 3.4


# Install

1. Install dependencies
    
    sudo apt-get install redis-server python 3.4

1. create a virtualenv

    mkvirtualenv addok --python=/usr/bin/python3.4

1. install python packages

    pip install -r requirements.txt


# Import data

1. Download [BANO data](http://bano.openstreetmap.fr/data/bano-full.csv.gz)

2. Run import command

    python run.py import path/to/bano-full.csv

If you only want a subset of the data, you can extract it from full file with
a command like:

    sed -n 's/|Île-de-France|/&/p' ~/Data/geo/bano/bano-full.csv > idf.csv


# Shell

Addok comes with a built-in shell that allows you to inspect the internals of 
addok:

    python run.py shell


# Serve

Addok exposes an experimental WSGI interface, you can run it with gunicorn
for example:

    gunicorn addok.server:app

For debug, you can run the simple Werzeug server:

    python run.py serve
