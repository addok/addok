# Addok

Search engine for address. Only address.

Addok will index your address data and provide an HTTP API for full text search.

It is extensible with [plugins](http://addok.readthedocs.io/en/latest/plugins/),
for example for geocoding CSV files.

Used in production by France administration, with around 26 millions addresses.
In those servers, full France data is imported in about 15 min and it scales
to around 2000 searches per second.

Check the [documentation](http://addok.readthedocs.org/en/latest/) and a
[demo](http://adresse.data.gouv.fr/map) with French data.

For discussions, please use the [discourse Geocommun forum](https://forum.geocommuns.fr/c/adresses/addok-le-geocodeur/17). Discussions are mostly French, but English is very welcome.

Powered by Python and Redis.

[![PyPi version](https://img.shields.io/pypi/v/addok.svg)](https://pypi.python.org/pypi/addok/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/addok)
[![Coverage Status](https://coveralls.io/repos/addok/addok/badge.svg?branch=main&service=github)](https://coveralls.io/github/addok/addok?branch=main)
