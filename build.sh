#!/bin/bash

# Build artefacts required by http://download.xcsoar.org/.

# Halt on errors:
set -e

# Check for arguments
if [ $# -eq 0 ]; then
    echo "No arguments provided:"
    echo "USAGE:"
    echo "$0 OUTPUT_DIR"
    echo -n ""
    exit 1
fi

## Output directory:
OUT="${1}"

# Create DIR structure
mkdir -p "${OUT}"
mkdir -p "${OUT}"/content/airspace/{0_META,country,region,global}
mkdir -p "${OUT}"/content/waypoint/{0_META,country,region,global}
mkdir -p "${OUT}"/source/map/{0_META,country,region,global}

# Rsync static content
rsync -apt data/content/ ${OUT}/content/

# Web site artefacts: waypoints
./script/build/waypoints_js.py  data/content/waypoint/country/ "${OUT}/content/waypoint/0_META/"

# Concatenate all waypoints to xcsoar-waypoints.cup
CUPHEADER=name,code,country,lat,lon,elev,style,rwdir,rwlen,freq,desc
echo "${CUPHEADER}"  > "${OUT}/content/waypoint/global/xcsoar_waypoints.cup"
for each in $(find data/content/waypoint/country/ -name "*.cup")
  do
    dos2unix "${each}"
    cat "${each}" | grep -v "${CUPHEADER}" | sort -b >> "${OUT}/content/waypoint/global/xcsoar_waypoints.cup"
done

# Web site artefacts: maps
./script/build/maps_config_js.py "${OUT}/source/map/0_META/"

# Build maps if needed
bash -x ./script/build/generate_maps.sh "${OUT}"

# XCSoar App's manifest file (https://download.xcsoar.org/repository)
./script/build/repository.py "${OUT}"
