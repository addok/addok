import os
from pathlib import Path

REDIS = {
    'host': 'localhost',
    'port': 6379,
    'db': 0
}


# Max number of results to be retrieved from db and scored.
BUCKET_LIMIT = 100

# Above this treshold, terms are considered commons.
COMMON_THRESHOLD = 10000

# Above this treshold, we avoid intersecting sets.
INTERSECT_LIMIT = 100000

# Min score considered matching the query.
MATCH_THRESHOLD = 0.9

GEOHASH_PRECISION = 8

RESOURCES_ROOT = Path(__file__).parent.parent.joinpath('resources')
SYNONYMS_PATH = RESOURCES_ROOT.joinpath('synonyms').joinpath('fr.txt')

# Pipeline stream to be used.
PROCESSORS = [
    'addok.textutils.default.pipeline.tokenize',
    'addok.textutils.default.pipeline.normalize',
    'addok.textutils.default.pipeline.synonymize',
    'addok.textutils.fr.phonemicize',
]
QUERY_PROCESSORS = (
    'addok.textutils.fr_FR.extract_address',
    'addok.textutils.fr_FR.clean_query',
    'addok.textutils.fr_FR.glue_ordinal',
)
BATCH_PROCESSORS = (
    'addok.batch.default.to_json',
)


# Fields to be indexed
# If you want a housenumbers field but need to name it differently, just add
# type="housenumbers" to your field.
FIELDS = [
    {'key': 'name', 'boost': 4, 'null': False},
    {'key': 'street'},
    {'key': 'postcode',
     'boost': lambda doc: 1.2 if doc.get('type') == 'commune' else 1},
    {'key': 'city'},
    {'key': 'housenumbers'}
]

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

LOG_BATCH_QUERIES = False
LOG_NOT_FOUND = False

PSQL = {
    'dbname': 'nominatim'
}
PSQL_PROCESSORS = (
    'addok.batch.psql.query',
    'addok.batch.nominatim.get_context',
    'addok.batch.nominatim.get_housenumbers',
    'addok.batch.nominatim.row_to_doc',
)
PSQL_QUERY = """SELECT osm_type,osm_id,class,type,admin_level,rank_search,
             place_id,parent_place_id,street,postcode,
             (extratags->'ref') as ref,
             ST_X(ST_Centroid(geometry)) as lon,
             ST_Y(ST_Centroid(geometry)) as lat,
             name->'name' as name, name->'short_name' as short_name,
             name->'official_name' as official_name,
             name->'alt_name' as alt_name
             FROM placex
             WHERE name ? 'name'
             {extrawhere}
             ORDER BY place_id
             {limit}
             """
PSQL_EXTRAWHERE = ''
# If you only want addresses
# PSQL_EXTRAWHERE = "AND class='highway' AND osm_type='W'"
# If you don't want any address
# PSQL_EXTRAWHERE = ("AND (class!='highway' OR osm_type='W') "
#                    "AND class!='place'")

PSQL_LIMIT = None
PSQL_ITERSIZE = 1000
