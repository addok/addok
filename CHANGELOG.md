## 0.3.1

- fix single character wrongly glued to housenumber ([#99](https://github.com/etalab/addok/issues/99))

## 0.3.0

- use housenumber id as result id, when given ([#38](https://github.com/etalab/addok/issues/38))
- shell: warn when requested id does not exist ([#75](https://github.com/etalab/addok/issues/75))
- print filters in debug mode
- added filters to CSV endpoint ([#67](https://github.com/etalab/addok/issues/67))
- also accept `lng` as parameter ([#88](https://github.com/etalab/addok/issues/88))
- add `/get/` endpoint ([#87](https://github.com/etalab/addok/issues/87))
- display distance in meters (not kilometers)
- add distance in single `/reverse/` call
- workaround python badly sniffing csv file with only one column ([#90](https://github.com/etalab/addok/issues/90))
- add housenumber in csv results ([#91](https://github.com/etalab/addok/issues/91))
- CSV: renamed "result_address" to "result_label" ([#92](https://github.com/etalab/addok/issues/92))
- no BOM by default in UTF-8
