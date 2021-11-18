#!/bin/bash

# Verify integrity and genereate artefacts required by http://download.xcsoar.org/.

# Halt on errors:
set -e
# Echo commands:
set -x

# Install dependencies:
pip3 install -U aerofiles
pip3 install -U iso3166

# CHECK: waypoints/country
./scripts/check_waypoints_country.py waypoints

# CHECK: waypoints/special
for each in waypoints-special/*.cup ; do python ./scripts/check-waypoints "${each}" ; done

# GENERATE: Release artefacts
./scripts/generate-web-waypoints-index.py  waypoints waypoints

# GENERATE: Concatenate all waypoints to xcsoar-waypoints.cup
cat waypoints/*.cup | sort -b > waypoints/xcsoar_waypoints.cup
