#!/bin/bash

# Verify integrity.
ERROR=0
OUT="${1}"

# Set default to output if not specified
if [ -z "${OUT}" ]; then
  OUT="./output/content"
fi

# report all errors don't halt.
if ! ./script/check/check_waypoints_country.py "${OUT}"/waypoint/country/*.cup; then
  ERROR=1
fi

while IFS= read -r -d '' each; do
  if ! ./script/check/check_waypoints.py "${each}"; then
    ERROR=1
  fi
done < <(find "${OUT}/waypoint/" -type f -name "*.cup" -print0)

if ! ./script/check/check_airspaces.py "${OUT}"/airspace/; then
  ERROR=1
fi

if ! ./script/check/check_urls.py "${OUT}"/repository; then
  ERROR=1
fi

if [ "${ERROR}" = '1' ]; then
   echo "There where errors."
   exit 1
fi
