# Welcome to Addok documentation

*Search engine for address. Only address.*

## Overview

Addok works with Redis as backend.

- it imports and indexes your data (can also import from Nominatim database) from command line
- it serves a minimal GeoJSON based API (with Falcon)
- it does reverse geocoding
- it does batch geocoding (through CSV)
- it has a debug shell for inspecting the index
- it's configurable in many details
- it's extendable by plugins
- it's open source

Start by [installing it](install.md) and understand underlying [concepts](concepts.md).

## Show me the code

The code is published via [Github](https://github.com/addok/addok/).

## Licence

Addok is released under the MIT Licence.
