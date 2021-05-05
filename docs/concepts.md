# Concepts

Addok is a [geocoder](https://en.wikipedia.org/wiki/Geocoding). It allows to look for structured geographical documents from an unstructured string.


## Data

Addok accepts batch loading of geo-related documents like addresses. At least latitude and longitude are required for each indexed document. Even once loaded, data should not be considered as your reference but versatile, each reindexation requires initial source files to be loaded again.

By default, a Redis database° stores indexes while another one is storing raw documents. All data stored into Redis means it is stored into memory. You can install a [plugin](plugins.md) to keep documents within another database engine (SQLite or PostgreSQL for instance) to save memory.

° addok has also been tested with Redis fork like KeyDB. All references to Redis in this documentation also apply to KeyDB.


## Indexation

Each document goes through several processors defined in your [configuration file](config.md). There are two main steps to handle a document: strings preparation and indexes computation.

The document is split into tokens (by default words but it can be trigrams when using [addok-trigrams](https://github.com/addok/addok-trigrams) plugin). Each token becomes an item in a [Redis sorted set](https://redis.io/topics/data-types#sorted-sets) storing the list of documents containing that token. Filters and geographical properties will also be stored as Redis sorted sets. A search query consists of intersections of these defined sets.


## Search

Search is a three-steps process:
1) we clean and put into tokens the query (with same processors as during indexation),
2) then we try to find all candidates for a given query,
3) finally we iterate to order results by relevance.

Through heuristics, we try to find a reasonable number of candidates (about 100) dealing with noise, typos and wrong input. Once the candidates are retrieved, they are ordered mainly by string comparisons with the original searched text.

Documents importances and geographical positions may also be taken into account. Additionally, a query can be explicitly filtered by the issuer based on documents’ fields to restrain the number of potential results.


## HTTP API

Addok provides an [API](api.md) to query the indexed data via HTTP. It has been developed with performance as a key constraint. By default, it serves results as *flat* [GeoCodeJSON](https://github.com/geocoders/geocodejson-spec/).

The API has three entry points by default but you can extend it. One is to perform a search query, the second is about reverse geocoding (see below) and the last one is for retrieving a document.

You can perform a search query with a geographical bias, boosting candidates around a given location. Besides, it allows for reverse geocoding: from a location to the closest known address for instance.


## Hacking

A custom binary launches a [shell interpreter](shell.md) with a couple of useful commands to debug and understand how it works. For instance, you can explain a given result, shows autocomplete results for a given token, inspect how a string is put into tokens and so on. Oh, and of course, perform a search!

Even if Addok focuses on the particular problem of addresses — trying to do one job and to (hopefully) do it well — it has been developed with extensibility in mind. You can enrich it for your own use with [plugins](plugins.md) and/or [API](api.md) entry points.

See also this
[presentation](https://speakerdeck.com/yohanboniface/addok-presentation) for more details.
