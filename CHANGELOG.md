## 1.2.0 (2025-06-01)

- Add Python 3.12 and 3.13 support
- Update `falcon` to 4.0.2
- Update multiple small dependencies
- Some minor code improvements
- Drop Cython support
- Drop Python 3.7 and 3.8 support (end of life since 27 Jun 2023 and 7 Oct 2024)

## 1.1.2 (2024-01-26)

- Improve values handling in index and deindex methods (#798)

## 1.1.1

- Make `addok ngrams` work again on macOS
- Disable multiprocessing on macOS (affect only ngrams generation)
- Update `redis` to 4.5.4 and `hiredis` to `2.2.2`

## 1.1.0

- Drop Python 3.6 support (end of life since 23 Dec 2021)
- Added `/health` endpoint to monitor Addok (#[750](https://github.com/addok/addok/issues/750))

## 1.1.0-rc2

- Added `load_csv_file` batch loader
- Fixed `type=housenumber` also returning other results in some cases (#[478](https://github.com/addok/addok/issues/478))
- Fixed ordering of housenumbers with non alpha-num chars (#[656](https://github.com/addok/addok/issues/656))
- Added `ID_FIELD` to control which field is used as document `_id`
- `config.SYNONYMS_PATH` is now `config.SYNONYMS_PATHS` and is a list to allow
  multiple files
- Fixed non unique id across multiple docker sharing same Redis instance (#[607](https://github.com/addok/addok/issues/607))
- Added more variants for `lat` and `lon` params and better control their values (#[592](https://github.com/addok/addok/issues/592))
- Better ordering of candidates in case of autocomplete (#[494](https://github.com/addok/addok/issues/494))
- By default, use more common chars when building fuzzy variants
- Added python >= 3.8 compat
- Restore legacy scoring algorithm (#[746](https://github.com/addok/addok/issues/746)): the new experimental scoring must be
  activated manually, replacing `addok.helpers.results.score_by_ngram_distance` with
  `addok.helpers.results.score_by_str_distance` in `SEARCH_RESULT_PROCESSORS_PYPATHS`


## 1.1.0-rc1

- Faster new scoring algorithm (#[431](https://github.com/addok/addok/issues/431))
- Upgraded Falcon to 1.4.1
- `autocomplete` and `fuzzy` are not adding any more their collectors automagically,
  instead they are now hard coded in the default config; if you haven't changed
  `RESULTS_COLLECTORS_PYPATHS` in your local config this should not impact you,
  otherwise, see "Upgrading" below.
- Added a slow queries logger (see [config](config.md#slow_queries-integer) for usage)

### Upgrading to 1.1.0-rc1

If you have changed `RESULTS_COLLECTORS_PYPATHS` in your local config file, make
sure to add manually `fuzzy` and `autocomplete` ones. Check the
[config doc](config.md) for an example.

## 1.0.3

- make it work with python >= 3.8
- upgrade python deps

## 1.0.2

- allow to connect to Redis through unix socket
- fix reverse not honouring extra housenumber fields
- fix default BATCH_WORKERS values failing on systems with only one CPU

## 1.0.1

- Upgraded Falcon to 1.2.0
- Fix bug when search request is empty but lat and lon are given and valid
- Handle filters when doing a manual scan with Lua
- Allow to configure Redis password from config

## 1.0.0

The 1.0.0 has been a big rewrite, with main features:

- split in [plugins](http://addok.readthedocs.io/en/latest/plugins/)
- allow for external storage of documents (in SQLite, PostgreSQL, etc.)
- use LUA scripting for performances
- less RAM consumption
- replaced Flask by Falcon for performances
- housenumbers are not indexed anymore (to gain RAM), they are only matched in
  result postprocessing

It contains many breaking changes. Best option when possible is to restart
from scratch (see the [tutorial](http://addok.readthedocs.io/en/latest/tutorial/))
and reindex everything.

### Breaking changes

- `PROCESSORS`, `INDEXERS`, etc. have been renamed to `PROCESSORS_PYPATHS`,
  `INDEXERS_PYPATHS`, etc.
- `HOUSENUMBERS_PROCESSORS` have been removed
- config must now be loaded by `from addok.config import config`
- removed `DEINDEXERS`, now `INDEXERS` must point to python classes having both
  `index` and `deindex` methods
- endpoints API changed
- by default, documents are now stored in a separate Redis database
- the key "id" is not required anymore in the loaded data and as such has been
  removed from the geojson Feature root.

### Minor changes

- index multi values in filters
- add a "reset" command to reset all data (indexes and documents)
- added `quote` parameter for CSV endpoints (now in addok-csv plugin)
- addok now tries to read config from `/etc/addok/addok.conf` as fallback
- `SMALL_BUCKET_LIMIT` is now a setting

Also check the new [FAQ](http://addok.readthedocs.io/en/latest/faq/) section
in the documentation.


## 0.5.0
- Expose housenumber parent name in result geojson
- add support for housenumber payload ([#134](https://github.com/addok/addok/issues/134))
- Fix clean_query being too much greedy for "cs" ([#125](https://github.com/addok/addok/issues/125)
- also accept long for longitude
- replace "s/s" in French preprocessing
- fix autocomplete querystring casting to boolean
- Always add housenumber in label candidates if set ([#120](https://github.com/addok/addok/issues/120))
- make CSVView more hackable by plugins ([#116][https://github.com/addok/addok/issues/116))


## 0.4.0
- fix filters not taken into account in manual scan ([#105](https://github.com/addok/addok/issues/105))
- added experimental list support for document values
- Added MIN_EDGE_NGRAMS and MAX_EDGE_NGRAMS settings ([#102](https://github.com/addok/addok/issues/102))
- documented MAKE_LABELS setting
- Allow to pass functions as PROCESSORS, instead of path
- remove raw housenumbers returned in result properties
- do not consider filter if column is empty, in csv ([#109](https://github.com/addok/addok/issues/109))
- allow to pass lat and lon to define columns to be used for geo preference, in csv ([#110](https://github.com/addok/addok/issues/110))
- replace "s/" by "sur" in French preprocessing ([#107](https://github.com/addok/addok/issues/107))
- fix server failing when document was missing `importance` value
- refuse to load if `ADDOK_CONFIG_MODULE` is given but not found
- allow to set ADDOK_CONFIG_MODULE with command line parameter `--config`
- mention request parameters in geojson ([#113](https://github.com/addok/addok/issues/113))


## 0.3.1

- fix single character wrongly glued to housenumber ([#99](https://github.com/addok/addok/issues/99))

## 0.3.0

- use housenumber id as result id, when given ([#38](https://github.com/addok/addok/issues/38))
- shell: warn when requested id does not exist ([#75](https://github.com/addok/addok/issues/75))
- print filters in debug mode
- added filters to CSV endpoint ([#67](https://github.com/addok/addok/issues/67))
- also accept `lng` as parameter ([#88](https://github.com/addok/addok/issues/88))
- add `/get/` endpoint ([#87](https://github.com/addok/addok/issues/87))
- display distance in meters (not kilometers)
- add distance in single `/reverse/` call
- workaround python badly sniffing csv file with only one column ([#90](https://github.com/addok/addok/issues/90))
- add housenumber in csv results ([#91](https://github.com/addok/addok/issues/91))
- CSV: renamed "result_address" to "result_label" ([#92](https://github.com/addok/addok/issues/92))
- no BOM by default in UTF-8
