# Addok shell

Addok comes with a builtin shell, that allows to inspect the
internals of the index, tests queries and the string processing.
Consider it as a debug tool.

Enter in the shell with command:

    addok shell

Here are the available commands:

#### AUTOCOMPLETE
Shows autocomplete results for a given token.

    AUTOCOMPLETE lil

#### BESTSCORE
Return document linked to word with higher score.

    BESTSCORE lilas

#### BUCKET
Issue a search and return all the collected bucket, not only up to limit elements:

    BUCKET rue des Lilas

#### DBINFO
Print some useful infos from Redis DB.

#### DBKEY
Print raw content of a DB key.

    DBKEY g|u09tyzfe

#### DISTANCE
Print the distance score between two strings. Use | as separator.

    DISTANCE rue des lilas|porte des lilas

#### EXPLAIN
Issue a search with debug info:

    EXPLAIN rue des Lilas

#### FREQUENCY
Return word frequency in index.

    FREQUENCY lilas

#### FUZZY
Compute fuzzy extensions of word.

    FUZZY lilas

#### FUZZYINDEX
Compute fuzzy extensions of word that exist in index.

    FUZZYINDEX lilas

#### GEODISTANCE
Compute geodistance from a result to a point.

    GEODISTANCE 772210180J 48.1234 2.9876

#### GEOHASH
Compute a geohash from latitude and longitude.

    GEOHASH 48.1234 2.9876

#### GEOHASHMEMBERS
Return members of a geohash and its neighbors. Use "NEIGHBORS 0"
to only target geohash.

    GEOHASHMEMBERS u09vej04 [NEIGHBORS 0]

#### GEOHASHTOGEOJSON
Build GeoJSON corresponding to geohash given as parameter.

    GEOHASHTOGEOJSON u09vej04

#### GET
Get document from index with its id.

    GET 772210180J

#### HELP
Display the list of available commands.

#### INDEX
Get index details for a document by its id.

    INDEX 772210180J

#### INTERSECT
Do a raw intersect between tokens (default limit 100).

    INTERSECT rue des lilas [LIMIT 100]

#### PAIR
See all token associated with a given token.

    PAIR lilas

#### REVERSE
Do a reverse search. Args: lat lon.

    REVERSE 48.1234 2.9876

#### SEARCH
Issue a search (default command, can be omitted; arguments between `[]` are
optional):

    SEARCH rue des Lilas [CENTER lat lon] [LIMIT 10] [AUTOCOMPLETE 0]

Also, every registered filter is available, for example:

    rue des lilas CITY hautmont

#### TOKENIZE
Inspect how a string is tokenized before being indexed.

    TOKENIZE Rue des Lilas
