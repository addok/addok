# Configuring Addok

By default, Addok is configured for a French database of addresses from France
*(It may be because it has been initially coded in Paris… ;) )*

But certainly your needs are different, and even if you deal with French addresses
you may want to define **which fields are indexed** or **which filters are
available** for example.

*See algo [Redis Tuning](redis.md).*

## Registering your custom config file

An Addok config file is simply a python file that define some keys. The default
location is `/etc/addok/addok.conf`. But it can be anywhere else in your system,
and you need to define an environment variable that points to it if you want
a special location:

    export ADDOK_CONFIG_MODULE=path/to/local.py

You can also use the `--config` argument when running the `addok` command line.

## Environment settings

Some settings are used to define how addok will deal with the system it's
installed on.

#### REDIS (dict)
Defines the Redis database settings:

    REDIS = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }

By default, when using the `RedisStore` for documents, indexes and documents
will be stored in two different Redis databases.
You can control those details by using `indexes` and/or `documents`
subdictionnaries, for example:

    REDIS = {
        'host': 'myhost',
        'port': 6379,
        'indexes': {
            'db': 11,
        },
        'documents': {
            'db': 12,
        }
    }

If your hosts are different, you can define them like this:

    REDIS = {
        'port': 6379,
        'indexes': {
            'host': 'myhost1',
            'db': 11,
        },
        'documents': {
            'db': 12,
            'host': 'myhost2',
        }
    }

And of course, same for the port.


#### LOG_DIR (path)
Path to the directory Addok will write its log and history files. Can also
be overriden from the environment variable `ADDOK_LOG_DIR`.

    LOG_DIR = 'path/to/dir'

This setting defaults to the root folder of the addok package.


## Basic settings

A bunch of settings you may want to change to fit your custom instance.

#### ATTRIBUTION (string or dict)
The attribution of the data that will be used in the API results. Can be a
simple string, or a dict.

    ATTRIBUTION = 'OpenStreetMap Contributors'
    # Or
    ATTRIBUTION = {source: attribution, source2: attribution2}

#### EXTRA_FIELDS (list of dicts)
Sometimes you just want to extend [default fields](#fields-list-of-dicts).

    EXTRA_FIELDS = [
        {'key': 'myfield'},
    ]

#### FIELDS (list of dicts)
The document fields *you want to index*. It's a list of dict, each one defining
an indexed field. Available keys:

- **key** (*mandatory*): the key of the field in the document
- **boost**: optional boost of the field, define how important is the field
  in the index, for example one usually define a greater boost for *name* field
  than for *city* field (default: 1)
- **null**: define if the field can be null (default: True)

```
FIELDS = [
    {'key': 'name', 'boost': 4, 'null': False},
    {'key': 'street'},
    {'key': 'postcode',
     'boost': lambda doc: 1.2 if doc.get('type') == 'commune' else 1},
    {'key': 'city'},
    {'key': 'housenumbers'}
]
```

#### FILTERS (list)
A list of fields to be indexed as available filters. Keep in mind that every
filter means bigger index.

    FILTERS = ["type", "postcode"]

#### HOUSENUMBERS_PAYLOAD_FIELDS (list of keys)
If you want to store extra fields with each payload. Those fields will not
be searchable, but will be returned in the search result.

    HOUSENUMBERS_PAYLOAD_FIELDS = ['key1', 'key2']

#### LICENCE (string or dict)
The licence of the data returned by the API. Can be a simple string, or a dict.

    LICENCE = "ODbL"
    # Or
    LICENCE = {source: licence, source2: licence2}

#### LOG_QUERIES (boolean)
Turn this to `True` to log every query received and firt result if any. *Note:
only the queries are logged, not any of the other received data.*

    LOG_QUERIES = False

#### LOG_NOT_FOUND (boolean)
Turn this to `True` to log every not found query both through the `search`
endpoint or the `csv` one.

    LOG_NOT_FOUND = False

#### PROCESSORS_PYPATHS (iterable of python paths)
Define the various functions to preprocess the text, before indexing and
searching. It's an `iterable` of python paths. Some functions are built in
(mainly for French at this time, but you can point to any python function that
is on the pythonpath).

    PROCESSORS_PYPATHS = [
        'addok.textutils.default.pipeline.tokenize',
        'addok.textutils.default.pipeline.normalize',
        'addok.textutils.default.pipeline.synonymize',
        'addok.textutils.fr.phonemicize',
    ]

#### QUERY_PROCESSORS_PYPATHS (iterable of python paths)
Additional processors that are run only at query time.

    QUERY_PROCESSORS_PYPATHS = (
        'addok.textutils.fr_FR.extract_address',
        'addok.textutils.fr_FR.clean_query',
        'addok.textutils.fr_FR.glue_ordinal',
    )

#### SYNONYMS_PATH (path)
Path to the synonym file. Synonyms file are in the format `av, ave => avenue`.

    SYNONYMS_PATH = '/path/to/synonyms.txt'

## Advanced settings

Those are internal settings. Change them with caution.

#### BUCKET_MIN (int)
The min number of items addok will try to fetch from Redis before scoring and
sorting them. Note that **this is not the number of returned results**.
This may impact performances a lot.

    BUCKET_MIN = 10

#### BUCKET_MAX (int)
The max number of items addok will try to fetch from Redis before scoring and
sorting them. Note that **this is not the number of returned results**.
This may impact performances a lot.

    BUCKET_MAX = 100

#### COMMON_THRESHOLD (int)
Above this treshold, terms are considered commons, and thus with less importance
in the search algorithm.

    COMMON_THRESHOLD = 10000

#### DEFAULT_BOOST (float)
Default score for the relation token to document.

    DEFAULT_BOOST = 1.0

#### DOCUMENT_SERIALIZER_PYPATH (path)
Path to the serializer to be used for storing documents. Must have `loads` and
`dumps` methods.

    DOCUMENT_SERIALIZER_PYPATH = 'addok.helpers.serializers.ZlibSerializer'

For a faster option (but using more RAM), use `marshal` instead.

    DOCUMENT_SERIALIZER_PYPATH = 'marshal'


#### GEOHASH_PRECISION (int)
Size of the geohash. The bigger the setting, the smaller the hash.
See [Geohash on Wikipedia](http://en.wikipedia.org/wiki/Geohash).

    GEOHASH_PRECISION = 8

#### IMPORTANCE_WEIGHT (float)
The max inherent score of a document in the final score.

    IMPORTANCE_WEIGHT = 0.1

#### INTERSECT_LIMIT (int)
Above this treshold, we avoid intersecting sets.

    INTERSECT_LIMIT = 100000

#### MAX_EDGE_NGRAMS (int)
Maximum length of computed edge ngrams.

    MAX_EDGE_NGRAMS = 20

#### MIN_EDGE_NGRAMS (int)
Minimum length of computed edge ngrams.

    MIN_EDGE_NGRAMS = 3

#### MAKE_LABELS (func)
Function to override labels built for string comparison with query
at scoring time. Takes a `result` object as argument and must return a
list of strings.

    MAKE_LABELS = lambda r: return [r.name + 'my custom thing']

#### MATCH_THRESHOLD (float between 0 and 1)
Min score used to consider a result may *match* the query.

    MATCH_THRESHOLD = 0.9
