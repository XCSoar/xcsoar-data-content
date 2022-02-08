## xcsoar-data-content

[![Repository URL checker](https://github.com/XCSoar/xcsoar-data-content/actions/workflows/check_repo_urls.yml/badge.svg)](https://github.com/XCSoar/xcsoar-data-content/actions/workflows/check_repo_urls.yml)

This repository currently maintains all the data necessary to create the [XCSoar](https://xcsoar.org)
File Manager application's [repository manifest file](http://download.xcsoar.org/repository) as well
as enable some [XCSoar website](https://xcsoar.org/download/data.html) functionality.


This data consists of:

1. `content`: The content itself, like:
   1. Waypoints
   2. Airspaces
2. `remote`: URLs to external content, like:
   1. Waypoints hosted on https://soaringweb.org/, etc.
3. `source`: Configuration parameters specifying how to generate content, like:
   1. map bounding box co-ordinates.

Within the above three parent directories, the child directories specify the XCSoar data type
(E.g.  `type=map` in [repository](http://download.xcsoar.org/repository) ).
This is fully specified by the directory name (e.g. `map`, `waypoint`, `airspace`, etc.)

The directory level below this, specifies the geographic area of the data, and is simply used to enforce various
validity checks.
For example, files in any `country` directories, must have a filename stem (filename *sans* extension) that is an
ISO3166.alpha2 country code (e.g. `AR`, `DE`, `ZA`, etc.).
This is used as the [repository](http://download.xcsoar.org/repository) `area` field.

Additionally, for files in `region` subdirectories, the [repository](http://download.xcsoar.org/repository) `area`
field will be best-effort extracted from the filename prefix (underscore separated).
E.g. `ca_quebec.*` implies Canada.

The [repository's](http://download.xcsoar.org/repository) `update` field is generated from the git commit date.


### Output

The following manifest files are built by, with, and from, this repo (required by ...):

1. https://download.xcsoar.org/repository (XCSoar)
1. https://download.xcsoar.org/waypoints/waypoints.js (website)
1. https://download.xcsoar.org/waypoints/waypoints_compact.js (website)
1. https://download.xcsoar.org/maps/maps.config.js (website & `mapgen`)
1. https://download.xcsoar.org/waypoints/xcsoar_waypoints.cup (`mapgen`)



### Contributions

Please feel free to add missing data and correct errors by submitting a
[pull request](https://help.github.com/en/articles/creating-a-pull-request)!

When doing so, please write in the comments the source of the new  data, so that it is easy to verify.

Contributions here have to pass:

1. A review by another contributer
2. A parsing check by [aerofiles](https://github.com/Turbo87/aerofiles)
3. Validity check depending on file type. E.g. remote URLs must exist, file extensions must be correct, etc.
Please look in and run [script/check/check.bash](script/check/check.bash) to verify validity.

They are then merged, built, and deployed to https://download.xcsoar.org .
