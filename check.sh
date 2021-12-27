#!/bin/bash

# Verify integrity.

# Check for arguments
if [ $# -eq 0 ]; then
    echo "No arguments provided:"
    echo "USAGE:"
    echo "$0 OUTPUT_DIR"
    echo -n "" 
    exit 1
fi

# report all errors don't halt. 
./script/check/check_waypoints_country.py "${1}"/waypoint/country/*.cup
if [ "$?" != '0' ]; then
  ERROR=1;
fi

for each in $(find "${1}/waypoint/" -type f -name "*.cup")
  do 
    ./script/check/check_waypoints.py "${each}"
done
if [ "$?" != '0' ]; then
  ERROR=1;
fi

./script/check/check_airspaces.py "${1}"/airspace/
if [ "$?" != '0' ]; then
  ERROR=1;
fi

./script/check/check_urls.py "${1}"/repository
if [ "$?" != '0' ]; then
  ERROR=1;
fi

if [ "${ERROR}" = '1' ]; then 
   echo "There where errors."
   exit 1
fi
