import os
from pathlib import Path

REDIS = {
    'host': os.environ.get('REDIS_HOST') or 'localhost',
    'port': os.environ.get('REDIS_PORT') or 6379,
    'indexes': {
        'db': os.environ.get('REDIS_DB_INDEXES') or 0,
    },
    'documents': {
        'db': os.environ.get('REDIS_DB_DOCUMENTS') or 1,
    }
}

# Min/max number of results to be retrieved from db and scored.
BUCKET_MIN = 10
BUCKET_MAX = 100

# Above this treshold, terms are considered commons.
COMMON_THRESHOLD = 10000

# Above this treshold, we avoid intersecting sets.
INTERSECT_LIMIT = 100000

# Min score considered matching the query.
MATCH_THRESHOLD = 0.9

GEOHASH_PRECISION = 7

MIN_EDGE_NGRAMS = 3
MAX_EDGE_NGRAMS = 20

SYNONYMS_PATH = None

# Pipeline stream to be used.
PROCESSORS_PYPATHS = [  # Rename in TOKEN_PROCESSORS / STRING_PROCESSORS?
    'addok.helpers.text.tokenize',
    'addok.helpers.text.normalize',
    'addok.helpers.text.synonymize',
]
QUERY_PROCESSORS_PYPATHS = []
# Remove SEARCH_PREFIXES.
SEARCH_PREPROCESSORS_PYPATHS = [
    'addok.helpers.search.tokenize',
    'addok.helpers.search.search_tokens',
    'addok.helpers.search.select_tokens',
    'addok.helpers.search.set_should_match_threshold',
]
BATCH_PROCESSORS_PYPATHS = [
    'addok.batch.to_json',
    'addok.helpers.index.prepare_housenumbers',
    'addok.ds.store_documents',
    'addok.helpers.index.index_documents',
]
BATCH_FILE_LOADER_PYPATH = 'addok.helpers.load_file'
BATCH_CHUNK_SIZE = 1000
# During imports, workers are consuming RAM;
# let one process free for Redis by default.
BATCH_WORKERS = os.cpu_count() - 1
RESULTS_COLLECTORS_PYPATHS = [
    'addok.helpers.collectors.only_commons',
    'addok.helpers.collectors.bucket_with_meaningful',
    'addok.helpers.collectors.reduce_with_other_commons',
    'addok.helpers.collectors.ensure_geohash_results_are_included_if_center_is_given',  # noqa
    'addok.helpers.collectors.extend_results_reducing_tokens',
    'addok.helpers.collectors.extend_results_extrapoling_relations',
]
SEARCH_RESULT_PROCESSORS_PYPATHS = [
    'addok.helpers.results.match_housenumber',
    'addok.helpers.results.make_labels',
    'addok.helpers.results.score_by_importance',
    'addok.helpers.results.score_by_autocomplete_distance',
    'addok.helpers.results.score_by_ngram_distance',
    'addok.helpers.results.score_by_geo_distance',
]
REVERSE_RESULT_PROCESSORS_PYPATHS = [
    'addok.helpers.results.load_closer',
    'addok.helpers.results.make_labels',
    'addok.helpers.results.score_by_geo_distance',
]
RESULTS_FORMATTERS_PYPATHS = [
    'addok.helpers.formatters.geojson',
]
INDEXERS_PYPATHS = [
    'addok.helpers.index.HousenumbersIndexer',
    'addok.helpers.index.FieldsIndexer',
    # Both pairs indexers must be after `FieldsIndexer`.
    'addok.pairs.PairsIndexer',
    'addok.pairs.HousenumbersPairsIndexer',
    # Edge ngram indexer must be after `FieldsIndexer`.
    'addok.autocomplete.EdgeNgramIndexer',
    'addok.helpers.index.FiltersIndexer',
    'addok.helpers.index.GeohashIndexer',
]
# Any object like instance having `loads` and `dumps` methods.
DOCUMENT_SERIALIZER_PYPATH = 'addok.helpers.serializers.ZlibSerializer'

DOCUMENT_STORE_PYPATH = 'addok.ds.RedisStore'

# Fields to be indexed
# If you want a housenumbers field but need to name it differently, just add
# type="housenumbers" to your field.
FIELDS = [
    {'key': 'name', 'boost': 4, 'null': False},
    {'key': 'street'},
    {'key': 'postcode',
     'boost': lambda doc: 1.2 if doc.get('type') == 'commune' else 1},
    {'key': 'city'},
    {'key': 'housenumbers'},
    {'key': 'context'},
]

# Sometimes you only want to add some fields keeping the default ones.
EXTRA_FIELDS = []

# Weight of a document own importance:
IMPORTANCE_WEIGHT = 0.1

# Default score for the relation token => document
DEFAULT_BOOST = 1.0

# Data attribution
# Can also be an object {source: attribution}
ATTRIBUTION = "BANO"

# Data licence
# Can also be an object {source: licence}
LICENCE = "ODbL"

# Available filters (remember that every filter means bigger index)
FILTERS = ["type", "postcode"]

LOG_DIR = os.environ.get("ADDOK_LOG_DIR", Path(__file__).parent.parent.parent)

LOG_QUERIES = False
LOG_NOT_FOUND = False

INDEX_EDGE_NGRAMS = True
