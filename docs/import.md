# Batch importing data in Addok

## Import format

By default, Addok expect a [line delimited JSON stream](http://en.wikipedia.org/wiki/JSON_Streaming)
as input file. This means *one JSON object per line*.
Optionally, it's possible to use msgpack (for that, install `msgpack-python`
and adapt the value of the `BATCH_FILE_LOADER_PYPATH` configuration key) or csv.


#### Keys
The expected keys are the ones declared in the `FIELDS` attribute of your
[configuration](config.md), plus some special cases:

- **type** is expected even if not declared as index field
- **importance** is expected; must be a `float` between 0 and 1
- **_id** is optional and for internal use only, if not present a [hashid](http://hashids.org/)
  will be generated; note that shorter keys lead to smaller memory consumption on the Redis side
- **lat** and **lon** are expected
- **housenumbers** has a special format: `{number: {lat: yyy, lon: xxx}}` (optionally you can
  add any custom attribute)

Each value can be either a unique value or a list of values. In the latter case,
the first value will be considered as the active one (for example to display the label),
the optional other ones are considered as aliases.
They will be indexed and searchable though.

#### Example

    {"id": "091220245G","type": "street","name": "Chemin du Capitany","postcode": "09000","lat": "42.985755","lon": "1.620815","city": "Foix","departement": "Ariège", "region": "Midi-Pyrénées","importance": 0.4330 ,"housenumbers":{"13": {"lat": 42.984811,"lon": 1.620876},"15": {"lat": 42.984753,"lon": 1.620853},"39": {"lat": 42.983546,"lon": 1.621076},"8": {"lat": 42.985458,"lon": 1.621405},"23": {"lat": 42.984555,"lon": 1.620902},"29": {"lat": 42.984316,"lon": 1.620935},"37": {"lat": 42.983634,"lon": 1.621068},"19": {"lat": 42.984621,"lon": 1.620882},"33": {"lat": 42.983977,"lon": 1.621015},"6": {"lat": 42.985452,"lon": 1.621171},"25": {"lat": 42.984532,"lon": 1.620908},"21": {"lat": 42.984577,"lon": 1.620895},"1": {"lat": 42.986563,"lon": 1.620000},"11bis": {"lat": 42.985138,"lon": 1.621094},"17": {"lat": 42.984682,"lon": 1.620868},"3": {"lat": 42.986394,"lon": 1.620150}}}
    {"id": "091220259X","type": "street","name": "Avenue du Cardié","postcode": "09000","lat": "42.964308","lon": "1.595493","city": "Foix","departement": "Ariège", "region": "Midi-Pyrénées","importance": 0.4447 ,"housenumbers":{"13": {"lat": 42.964574,"lon": 1.595418},"19": {"lat": 42.964575,"lon": 1.595455},"15": {"lat": 42.964575,"lon": 1.595431},"6": {"lat": 42.964263,"lon": 1.595222},"1bis": {"lat": 42.964322,"lon": 1.596193},"17": {"lat": 42.964575,"lon": 1.595443},"23": {"lat": 42.964298,"lon": 1.594952},"27": {"lat": 42.964245,"lon": 1.594844},"1": {"lat": 42.964357,"lon": 1.596028},"2bis": {"lat": 42.964245,"lon": 1.596177},"4": {"lat": 42.964279,"lon": 1.595486},"2": {"lat": 42.964291,"lon": 1.595999},"8": {"lat": 42.964250,"lon": 1.595043},"5": {"lat": 42.964572,"lon": 1.595620},"33": {"lat": 42.963863,"lon": 1.594884},"9": {"lat": 42.964574,"lon": 1.595389},"31": {"lat": 42.964156,"lon": 1.594847},"21": {"lat": 42.964314,"lon": 1.595171},"11": {"lat": 42.964574,"lon": 1.595406},"7": {"lat": 42.964342,"lon": 1.595551},"35": {"lat": 42.963611,"lon": 1.594916},"3": {"lat": 42.964366,"lon": 1.595803},"25": {"lat": 42.964272,"lon": 1.594840}}}

#### Update and delete

If you want to manage diffs, you can add an `_action` key with one of the
following values:

- `update`: will first deindex document
- `delete`: will deindex document; only key `id` is required then

#### Tuning Redis

Make sure to check the [Redis tuning tips](redis.md).


#### Command line
To run the actual import:

    addok batch path/to/file.sjson

Then you need to index ngrams:

    addok ngrams


### Example with BANO

1. Download [BANO data](http://bano.openstreetmap.fr/data/full.sjson.gz) and
   uncompress it

2. Run batch command:

        addok batch path/to/full.sjson

3. Index edge ngrams:

        addok ngrams

If you only want a subset of the data (the whole BANO dataset requires 20GB of RAM),
you can extract it from full file with a command like:

    sed -n 's/"Île-de-France"/&/p' path/to/full.sjson > idf.sjson


## Import from PostgreSQL


See [addok-psql](https://github.com/addok/addok-psql) plugin.


## Read from stdin

`import` command can read from stdin, for example:

    $ addok batch < ~/Data/geo/ban/communes-context.json

Or:

    $ less ~/Data/geo/ban/communes-context.json | addok batch

## More options

Run `addok --help` to see the available options.
