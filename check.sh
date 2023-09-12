#!/bin/bash

# Verify integrity.

# Set default to output if not specified
if [ -z "${OUT}" ]; then
  OUT="./output/content"
fi

# report all errors don't halt.
./script/check/check_waypoints_country.py "${OUT}"/waypoint/country/*.cup
if [ "$?" != '0' ]; then
  ERROR=1;
fi

for each in $(find "${OUT}/waypoint/" -type f -name "*.cup")
  do
    ./script/check/check_waypoints.py "${each}"
done
if [ "$?" != '0' ]; then
  ERROR=1;
fi

./script/check/check_airspaces.py "${OUT}"/airspace/
if [ "$?" != '0' ]; then
  ERROR=1;
fi

./script/check/check_urls.py "${OUT}"/repository
if [ "$?" != '0' ]; then
  ERROR=1;
fi

if [ "${ERROR}" = '1' ]; then
   echo "There where errors."
   exit 1
fi
