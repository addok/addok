# Advanced understanding of Addok engine

## Foreword

- [Addok presentation](https://speakerdeck.com/yohanboniface/addok-presentation)
- [Sous le capot du géocodeur addok](https://cq94.medium.com/sous-le-capot-du-g%C3%A9ocodeur-addok-398ce9b2b1fa) (in French)
- [Concepts](concepts.md)

## Importing

### What's a document ?

By default, Addok imports documents in ndjson, where one line (reformated) looks
like this:

```json
{
    "id": "22003_0120",
    "name": "Rue des Lilas",
    "postcode": "22100",
    "citycode": [
        "22003"
    ],
    "oldcitycode": null,
    "lon": -2.126067,
    "lat": 48.457051,
    "x": 321263.77,
    "y": 6829717.72,
    "city": [
        "Aucaleuc"
    ],
    "oldcity": null,
    "context": "22, Côtes-d'Armor, Bretagne",
    "type": "street",
    "importance": 0.3562,
    "housenumbers": {
        "1": {
            "id": "22003_0120_00001",
            "x": 321239.59,
            "y": 6829718.52,
            "lon": -2.126394,
            "lat": 48.457044
        },
        "2": {
            "id": "22003_0120_00002",
            "x": 321242.31,
            "y": 6829714.77,
            "lon": -2.126354,
            "lat": 48.457012
        },
        "4": {
            "id": "22003_0120_00004",
            "x": 321309.47,
            "y": 6829719.77,
            "lon": -2.125452,
            "lat": 48.457096
        }
    }
}
```

This document must match the `FIELDS` in the configuration, which looks like:

```
FIELDS = [
    {"key": "name", "boost": 4, "null": False},
    {"key": "street"},
    {"key": "city"},
    {"key": "housenumbers"},
    {"key": "context"},
]
```

Those are the fields that Addok will indexe, and that will be searchable. A document
can contain many other fields, which will be returned in the final response.

Addok wants at least a `name` field, which can either be named `name`, or have
another name and have the `type="name"` attribute, or be declared through the
`NAME_FIELD` configuration key.

If you want to control the internal document ids (usefull for reindexing, for example),
you need to either declare an `ID_FIELD`, or to have a field `_id` in the document,
or a field with the `type="id"` attribute.

See [configuration](config.md#fields-list-of-dicts) for more about this setting.

Also, see `BATCH_FILE_LOADER_PYPATH` to load other formats of files.

### Preparing

Before indexing, for each document, Addok will iterate over the `BATCH_PROCESSORS`, which
are by default:

```python
BATCH_PROCESSORS_PYPATHS = [
    "addok.batch.to_json",
    # Apply the string preprocessor to the housenumbers values, so they can be
    # searched like any other string. Eg. with addok-fr, "1" will be turned into
    # "un".
    "addok.helpers.index.prepare_housenumbers",
    # Asks to the documents store to actually store this given document.
    "addok.ds.store_documents",
    # Actually indexes the document.
    "addok.helpers.index.index_documents",
]
```

Those processors are to be used for preparing the data, before doing the index.
One may for example add another processor to compute the document importance
automatically based on another field (eg. population), or to derive from a json
structure to the final structure Addok expects, etc.

### Indexing

The indexing process is controlled by the configuration key `INDEXERS`, which
looks like:

```python
INDEXERS_PYPATHS = [
    "addok.helpers.index.HousenumbersIndexer",
    "addok.helpers.index.FieldsIndexer",
    # Pairs indexer must be after `FieldsIndexer`.
    "addok.pairs.PairsIndexer",
    # Edge ngram indexer must be after `FieldsIndexer`.
    "addok.autocomplete.EdgeNgramIndexer",
    "addok.helpers.index.FiltersIndexer",
    "addok.helpers.index.GeohashIndexer",
]
```

What does "indexing" means in details ? This will create keys and values in the
Redis database.

The main indexer is the `FieldsIndexer`. It will break down each fields in tokens
(small pieces of text, see "String processing" below) and create sorted sets in Redis.
Basically, each token will become a sorted set key, where the value will be the
document id, with a computed weight score (see "Computing weight" below).

For example, indexing the example document shown above will create an index
structure like this (non exhaustive; dumy score between parens):

w\|ru | w\|de | w\|lila | w\|aukaleuk
----- | ------ | ------- | -------
22003_0120 (1.008)   | 22003_0120 (1.008)  | 22003_0120 (1.008) | 22003_0120 (1.032)

Now if we also index a document `Rue des Lauriers` in the same city, the index
will look like this:

w\|ru | w\|de | w\|lila | w\|aukaleuk | w\|laurier
----- | ------ | ------- | -------| -------
22003_0120 (1.008)   | 22003_0120 (1.008)  | 22003_0120 (1.008) | 22003_0120 (1.032) |
22003_0100 (1.008)   | 22003_0100 (1.008)  |  | 22003_0100 (1.032) | 22003_0100 (1.032)

The `HousenumbersIndexer` and `GeohashIndexer` will create geohash index
entries, in order to perform geolocation bias and reverse search.

The `FiltersIndexer` will create sets with the values of the `FILTERS` configuration
key. Example with the previous documents:

| f\|citycode\|22003
| --------
| 22003_0120
| 22003_0100

The `PairsIndexer` and the `EdgeNgramIndexer` will not create the same index
structure: values will not be document ids. The `PairsIndexer` will index all
tokens that have been seen with a given token. Still with the same example, it
will looks like this:

p\|ru    | p\|de | p\|lila | p\|aukaleuk | p\|laurier
-----    | ------ | ------- | -------| -------
de       | lila     | de       | de       | de       |
lila     | ru       | ru       | ru       | ru       |
laurier  | laurier  | laurier  | laurier  | aukaleuk  |
aukaleuk | aukaleuk | aukaleuk | lila     | lila     |

This index will be used to target relevant tokens when trying to compute autocomplete
and fuzzy.

The `EdgeNgramIndexer` will list all tokens that starts with a given token. For
example:

n\|lil | n\|lau  | n\|laur  | n\|lauri  |
-----  | ----    | ----     | ----      |
lila   | laurier | laurier  | laurier   |


### Computing weight

When indexing, each document is associated to all the tokens (words) it contains.
This relation is weighted. For example, in France, streets are often called
`rue de Something`, but there is also a city called `Rue`. So if someone types
`rue` without any other info (no location bias, no filter…), we want to find
the city, and the thousands of streets are not relevant in this case.

This is why addok uses `sorted set` and not simple `set`.

This "boost" value is computed this way:
- a given field (as in `FIELDS`) can have a boost (which can also be a callable
  that takes the document as argument); so one may boost differently the `name`
  field (higher) than the `state` (lower), for example. Also, using a callable
  may allow to boost some field (eg. `citycode`) only for some document types
  (eg. `city`)
- a given document can have an importance (which is usually a property given
  in the dataset); this importance may for example be related to the size of the
  city, so a same street `rue des Lilas` (without any other context) will first
  return the street of a big city instead of a random small town
- those two first scores are added, then divided by the number of tokens in the
  indexed field. So for example `lilas` with return first the city `les lilas`
  than a street called `rue des lilas bleux`


### String processing

In Addok, each field value is splitted and reduced in small tokens, that are
roughly words cleaned. Addok core does a part of this work, but given it's often
language dependant, the most part is done in plugins (for French `addok-fr`).

This part is controlled by the `PROCESSORS`, which is by default:

```python
PROCESSORS_PYPATHS = [
    "addok.helpers.text.tokenize",
    "addok.helpers.text.normalize",
    "addok.helpers.text.flag_housenumber",
    "addok.helpers.text.synonymize",
]
```

The `tokenize` function will actually split the value in, say, actual instances
of `addok.helpers.text.Token`, which is roughly an extension of the python `str`,
with custom behaviour and properties (like the `position` in the initial string,
the original string value (before any cleaning), or many helpers to compute the
frequency in the index…).

The `normalize` helper will remove any diacritics and lower case all the tokens.

The `flag_housenumber` is a very minimal way of marking a token as a housenumber.
It is supposed to be overriden with country specific rules (which is done for
example in the `addok-france` plugin).

The `synonymize` will replace tokens by others, using mapping files set in the
configuration. This is also usually custom and business specific.

A classic France based Addok instance, will have those string processors:

```python
PROCESSORS_PYPATHS = [
    "addok.helpers.text.tokenize",
    "addok.helpers.text.normalize",
    "addok_france.glue_ordinal",
    "addok_france.fold_ordinal",
    "addok_france.flag_housenumber",
    "addok.helpers.text.synonymize",
    "addok_fr.phonemicize",
]
```

Where we can see:

- `glue_ordinal` and `fold_ordinal`, which will deal with `bis`, `ter` and so on
- an override of the default `flag_housenumber` helper
- a `phonemicize` helper, that will try to reduce a token to its phonem, so trying
  to remove the plural or such


## Searching

### Cleaning the input

Before trying to search in the index, Addok will clean the human input. While
the document values during the import phase is supposed to be clean (eg. no useless
words), this may not be the case when dealing with a value coming from humans.

This part is controlled by the `QUERY_PROCESSORS`. Here again, the core
Addok does very little, and let the plugin implement country and business specific
rules.

Here is a classic configuration for a France instance:

```python
QUERY_PROCESSORS_PYPATHS = [
    "addok.helpers.text.check_query_length",
    "addok_france.extract_address",
    "addok_france.clean_query",
    "addok_france.remove_leading_zeros",
]
```

Where `extract_address` and `clean_query` will try to extract the relevant part
of the address, excluding any useless information (like `bâtiment B` or `Cedex XX`).

### Preparing tokens

As first step, Addok we'll qualify each token, in order to separate them in:
- housenumber tokens
- common tokens (means very common in the index)
- not found tokens (so not in the index)
- other tokens, which are called "meaningfull tokens" in the code, and are
  considered the most relevant one to identify the search.

This first step is controlled by the configuration key `SEARCH_PREPROCESSORS`.


### Querying the index

Here is the core part of the "search".

Keep in mind that what we call "search" here (a.k.a. geocoding) consist in trying
to guess a structured document from an unstructured. The key word here is "guess".

This part is controlled by the `RESULTS_COLLECTORS`.

Here is what it looks like:

```python
RESULTS_COLLECTORS_PYPATHS = [
    "addok.autocomplete.only_commons_but_geohash_try_autocomplete_collector",
    "addok.helpers.collectors.no_tokens_but_housenumbers_and_geohash",
    "addok.helpers.collectors.no_available_tokens_abort",
    "addok.helpers.collectors.only_commons",
    "addok.autocomplete.no_meaningful_but_common_try_autocomplete_collector",
    "addok.autocomplete.only_commons_try_autocomplete_collector",
    "addok.helpers.collectors.bucket_with_meaningful",
    "addok.helpers.collectors.reduce_with_other_commons",
    "addok.helpers.collectors.ensure_geohash_results_are_included_if_center_is_given",  # noqa
    "addok.autocomplete.autocomplete_meaningful_collector",
    "addok.fuzzy.fuzzy_collector",
    "addok.helpers.collectors.extend_results_extrapoling_relations",
    "addok.helpers.collectors.extend_results_reducing_tokens",
]
```

The key concept to have in mind is that Addok will select some tokens and try to
make sorted set intersections in Redis. Remember that each sorted set has a token
(a word) as key, and document ids as values. So we basically ask Redis: do you
have some documents ids that are in all those sorted set, in other words: do you
know documents ids that have all those words.

All the results collection is just about trying and trying again with some
tokens, adding tokens or removing tokens, to adjust the collect results.

Addok calls the results collection a "bucket". It will try to fill in this bucket
until it has enough results.

Meanwhile it collect those results, it will compute a score (see "Scoring results"
below), in order to continue or not to collect, according to the "quality" of those
results. The "quality" result is internally called the "cream" (like in a bucket
of fresh milk).

So let's take a very minimal example, still based on the same documents we've
used before. Our index looks like this:

w\|ru | w\|de | w\|lila | w\|aukaleuk | w\|laurier
----- | ------ | ------- | -------| -------
22003_0120 (1.008)   | 22003_0120 (1.008)  | 22003_0120 (1.008) | 22003_0120 (1.032) |
22003_0100 (1.008)   | 22003_0100 (1.008)  |  | 22003_0100 (1.032) | 22003_0100 (1.008)

We certainly have others "rue des Lilas" in other cities.

Let's imagine someone searches "rue des lilas Aucaleuc". Addok will first qualify
the tokens, more or less like this:
- housenumber tokens: none
- common tokens: `ru`, `de` (those are very common in the index, which means that
  their sorted set have a lot of values)
- not found token: none
- meaningfull tokens: `lila`, `aukaleuk`

Then Addok will ask Redis an intersect between those two sorted sets: `w|lila` and
`w|aukaleuk`. It will find one document id.

At this stage, the bucket contains one result (we know it's the "good" result,
but Addok does not).

One result is not enough for Addok to have confidence it has searched
enough, so it will now try again with fewer tokens, so in this case, with only
one token, the less frequent between `w|lila` and `w|aukaleuk`.

It certainly will start by `aukaleuk`, because there is certainly fewer document
related to `Aucaleuc` city than documents related to `Lilas` in the whole country.

Those results will be added to the bucket. If the bucket contains less than
`config.BUCKET_MIN`, Addok will issue a new request with the other token.

Addok will again try to extract the "cream" from the bucket, and given it has
one good result (see "Scoring results"), and it has a bucket with enough results,
it will return the better scored results and stop here.

This is a very simple version of the bucket heuristic. Basically, each collector
from the `RESULTS_COLLECTORS` will:
- try to determine weither it whould act or not according to the bucket state:
    - is it empty ?
    - does it have few results (less than `config.BUCKET_MIN`) ?
    - does it overflow (more results than `config.BUCKET_MAX`) ?
    - does it have cream (results with score > `config.MATCH_THRESHOLD`)
- compute a set of keys to do an intersect in Redis
- add the results in the bucket
- let the next collector act

Each collector has its own heuristic, for example:

- `addok.autocomplete.only_commons_but_geohash_try_autocomplete_collector`: there
  are only common tokens (so high cost of intersect), but there is a location bias
  in the request, so let's intersect those common tokens PLUS the geohash set
- `addok.helpers.collectors.no_tokens_but_housenumbers_and_geohash` : very specific
  case for searches starting with a housenumber, like `8 rue des` when autocomplete
  is active.
- `addok.helpers.collectors.no_available_tokens_abort`: no usable token
- `addok.helpers.collectors.only_commons`: this is one of the main collectors,
  that deals with case where we have only common tokens
- `addok.fuzzy.fuzzy_collector`: we'll try to extend tokens with fuzzy matching
  to find more results in case the bucket is empty
- `addok.helpers.collectors.extend_results_extrapoling_relations`: that one tries
  to be smart finding the tokens that are more often seen together, so to do
  intersect with more chance of finding something
- `addok.helpers.collectors.extend_results_reducing_tokens`: that one is a bit
  of a broom wagon: we have found nothing until then, let's try with fewer tokens
- …

Example of a custom collector:

```python
from addok.helpers import keys


def target_city(helper):
    # Dumb way of targeting only cities when the search string is very small.
    if len(helper.query) <= 4 and not helper.autocomplete:
        helper.filters.append(keys.filter_key("municipality"))


RESULTS_COLLECTORS_PYPATHS = [
    "addok.autocomplete.only_commons_but_geohash_try_autocomplete_collector",
    ...,
    target_city,
    ...
]
```

### Filters

Filters are also indexed as `set` in Redis, and are used in the intersect when
collecting result.

Filters are fields that have been listed in the `FILTERS` configuration key.

Unlike indexed fields, the filters are not processed at all, and only perfect
match are considered.

### Scoring results

While collecting results, from time to time (when needing to know whether to
continue collecting or not), Addok will compute a score for each result.

This score is controlled by the `SEARCH_RESULT_PROCESSORS` configuration key.

This score is composed by:

- mainly, the string distance between the original searched string and some
  computed labels for the result
- a score based on importance of the document
- if location bias is included in the search, a score based on geographical distance

## Hacking with the shell

Addok comes with a shell to debug its internal and better understand its behaviour.

Here is an example of running a simple search:

```
$ addok shell
Addok 1.1.0rc1
Loaded local config from addok/config/local.py
Loaded plugins:
addok.shell==1.1.0rc1, addok.http.base==1.1.0rc1, addok.batch==1.1.0rc1, addok.pairs==1.1.0rc1, addok.fuzzy==1.1.0rc1, addok.autocomplete==1.1.0rc1, csv==1.1.0, addok_fr_admin==0.0.1, fr==1.0.1, france==1.1.3

Welcome to the Addok shell o/
Type HELP or ? to list commands.
Type QUIT or ctrl-C or ctrl-D to quit.

> rue des lilas
Rue des Lilas 75019 Paris (73Ow | 0.976310909090909)
Rue des Lilas 77500 Chelles (3r99 | 0.9700127272727271)
Rue des Lilas 22190 Plérin (r16B | 0.9618445454545452)
Rue des Lilas 77330 Ozoir-la-Ferrière (OZMg | 0.960891818181818)
Rue des Lilas 22440 Ploufragan (6qBz | 0.9599363636363636)
Rue des Lilas 22960 Plédran (G0Gy | 0.9592181818181817)
Rue des Lilas 22950 Trégueux (xmvr | 0.959041818181818)
Rue des Lilas 77700 Magny-le-Hongre (lD8V | 0.9575345454545454)
Rue des Lilas 77360 Vaires-sur-Marne (919P | 0.9572699999999998)
Rue des Lilas 22400 Lamballe-Armor (0wRK | 0.9571363636363636)
12.7 ms — 1 run(s) — 10 results
--------------------------------------------------------------------------------
```

Same search, but in EXPLAIN mode:

```
> EXPLAIN rue des lilas
[0.959] Taken tokens: [<Token lila>]
[0.982] Common tokens: [<Token ru>, <Token de>]
[0.984] Housenumbers token: []
[0.987] Not found tokens: []
[1.005] Filters: []
[1.011] ** TARGET_CITY **
[1.014] ** ONLY_COMMONS_BUT_GEOHASH_TRY_AUTOCOMPLETE_COLLECTOR **
[1.017] ** NO_TOKENS_BUT_HOUSENUMBERS_AND_GEOHASH **
[1.020] ** NO_AVAILABLE_TOKENS_ABORT **
[1.023] ** ONLY_COMMONS **
[1.026] ** NO_MEANINGFUL_BUT_COMMON_TRY_AUTOCOMPLETE_COLLECTOR **
[1.028] ** ONLY_COMMONS_TRY_AUTOCOMPLETE_COLLECTOR **
[1.031] ** BUCKET_WITH_MEANINGFUL **
[1.039] New bucket with keys ['w|lila', 'w|ru'] and limit 10
[1.443] 10 ids in bucket so far
[1.453] New bucket with keys ['w|lila', 'w|ru'] and limit 0
[1.814] 51 ids in bucket so far
[1.821] ** REDUCE_WITH_OTHER_COMMONS **
[1.830] ** ENSURE_GEOHASH_RESULTS_ARE_INCLUDED_IF_CENTER_IS_GIVEN **
[1.833] ** FUZZY_COLLECTOR **
[1.840] ** AUTOCOMPLETE_MEANINGFUL_COLLECTOR **
[1.845] Autocompleting lila
[2.019] No candidates. Aborting.
[2.023] ** EXTEND_RESULTS_EXTRAPOLING_RELATIONS **
[2.026] ** EXTEND_RESULTS_REDUCING_TOKENS **
[2.032] Computing results
[2.041] Done getting results data
[7.994] Done computing results
Rue des Lilas 75019 Paris (73Ow | importance: 0.0739/0.1, str_distance: 1.0/1.0)
Rue des Lilas 77500 Chelles (3r99 | importance: 0.067/0.1, str_distance: 1.0/1.0)
Rue des Lilas 22190 Plérin (r16B | importance: 0.058/0.1, str_distance: 1.0/1.0)
Rue des Lilas 77330 Ozoir-la-Ferrière (OZMg | importance: 0.057/0.1, str_distance: 1.0/1.0)
Rue des Lilas 22440 Ploufragan (6qBz | importance: 0.0559/0.1, str_distance: 1.0/1.0)
Rue des Lilas 22960 Plédran (G0Gy | importance: 0.0551/0.1, str_distance: 1.0/1.0)
Rue des Lilas 22950 Trégueux (xmvr | importance: 0.0549/0.1, str_distance: 1.0/1.0)
Rue des Lilas 77700 Magny-le-Hongre (lD8V | importance: 0.0533/0.1, str_distance: 1.0/1.0)
Rue des Lilas 77360 Vaires-sur-Marne (919P | importance: 0.053/0.1, str_distance: 1.0/1.0)
Rue des Lilas 22400 Lamballe-Armor (0wRK | importance: 0.0529/0.1, str_distance: 1.0/1.0)
8.3 ms — 1 run(s) — 10 results
--------------------------------------------------------------------------------
```
