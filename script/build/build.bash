#!/bin/bash

# Build artefacts required by http://download.xcsoar.org/.

# Halt on errors:
set -e
# Echo commands:
set -x

if [ $# -eq 0 ]; then
    set +x
    echo -e "No arguments provided:\n"
    echo -e "USAGE:"
    echo -e "$0 OUTPUT_DIR\n\n"
    exit 1
fi


# Install dependencies:
pip3 install -U aerofiles
pip3 install -U iso3166

## Output directory:
OUT=$1
mkdir -p "${OUT}"
#rm -rvf ${OUT}

# XCSoar App's manifest file (https://download.xcsoar.org/repository)
./script/build/repository.py "${OUT}"

# TODO:
# Transitional: the below artefacts should either be built in their respective repos
# (and often not on the public server), or at least be in a canonical data format like JSON.

# Web site artefacts: waypoints
./script/build/waypoints_js.py  data/content/waypoint/country/ "${OUT}/waypoints"

# Web site artefacts: maps
./script/build/maps_config_js.py "${OUT}/maps/"

# Concatenate all waypoints to xcsoar-waypoints.cup:  (TODO: include region, globe, etc.)
cat data/content/waypoint/country/*.cup | sort -b > "${OUT}/waypoints/xcsoar_waypoints.cup"
