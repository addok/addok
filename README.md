# Addok

Search engine for address. Only address.


# Dependencies

- Redis
- Python 3.4


# Install

1. Install dependencies
    
    sudo apt-get install redis-server python3.4 python-pip python-virtualenv

1. create a virtualenv

    mkvirtualenv addok --python=/usr/bin/python3.4

1. install python packages

    pip install -r requirements.txt


# Import data

1. Download [BANO data](http://bano.openstreetmap.fr/data/full.sjson.gz) and uncompress
   it

2. Run import command

    python run.py import path/to/full.sjson

3. Index edge ngrams

    python run.py ngrams

If you only want a subset of the data (the whole BANO dataset requires 20GB of RAM),
you can extract it from full file with a command like:

    sed -n 's/"Île-de-France"/&/p' path/to/full.sjson > idf.sjson


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
