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

# Rsync static content
rsync -apt --mkpath data/content/ "${OUT}/content/"

## REMOTE Stage
# add the openaip cup files
./script/build/xcsoar-openaip-generate-all-cup.py "${OUT}"

# Download weglide segments
./script/build/download-file.py "https://api.weglide.org/v1/segment/export?format=tsk" "${OUT}/content/task/global/" GLB-TSK-Segments-Weglide.tsk.json

## GENERATE Stage

# Web site artefacts: waypoints
./script/build/waypoints_js.py  data/content/waypoint/country/ "${OUT}/content/waypoint/0_META/"

# Concatenate all waypoints to xcsoar-waypoints.cup
CUPHEADER="name,code,country,lat,lon,elev,style,rwdir,rwlen,freq,desc"
XCSWAYPOINTSDIR="${OUT}/content/waypoint/global"
XCSWAYPOINTS="${XCSWAYPOINTSDIR}/xcsoar_waypoints.cup"
XCSWAYPOINTSTMP="$(mktemp)"
for each in $(find data/content/waypoint/country/ -name "*.cup")
  do
    dos2unix < "${each}" | grep -v "${CUPHEADER}" >> "${XCSWAYPOINTSTMP}"
done
mkdir -p "${XCSWAYPOINTSDIR}"
echo "${CUPHEADER}" > "${XCSWAYPOINTS}"
sort -bu "${XCSWAYPOINTSTMP}" >> "${XCSWAYPOINTS}"
rm "${XCSWAYPOINTSTMP}"


# Web site artefacts: maps
./script/build/maps_config_js.py "${OUT}/source/map/0_META/"

# Build maps if needed
bash -x ./script/build/generate_maps.sh "${OUT}"

## REPO Stage

# XCSoar App's manifest file (https://download.xcsoar.org/repository)
./script/build/repository.py "${OUT}"
./script/build/sortrepo.py "${OUT}"/repository > "${OUT}"/repository.sorted
mv "${OUT}"/repository.sorted "${OUT}"/repository
