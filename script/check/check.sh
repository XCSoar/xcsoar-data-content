#!/bin/bash

# Verify integrity.

# Halt on errors:
set -e
# Echo commands:
set -x

./script/check/check_waypoints_country.py data/content/waypoint/country/

for each in data/content/waypoint/region/*.cup; 
  do 
    python ./script/check/check-waypoints "${each}"
done
