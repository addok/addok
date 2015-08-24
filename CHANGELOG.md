# 0.3.0

- use housenumber id as result id, when given (#38)
- shell: warn when requested id does not exist (#75)
- print filters in debug mode
- added filters to CSV endpoint (#67)
- also accept `lng` as parameter (#88)
- add `/get/` endpoint (#87)
- display distance in meters (not kilometers)
- add distance in single `/reverse/` call
- workaround python badly sniffing csv file with only one column (#90)
- add housenumber in csv results (#91)
- CSV: renamed "result_address" to "result_label" (#92)
- no BOM by default in UTF-8
