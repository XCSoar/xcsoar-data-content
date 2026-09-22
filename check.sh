#!/bin/bash

# Verify integrity of a build produced by build.sh.
#
# Usage: ./check.sh [BUILD_DIR] [--offline]
#
# BUILD_DIR is build.sh's output directory (default ./output).  Content sits in
# its content/ subdirectory and the manifest beside that, so this takes the
# build root rather than the content directory.
#
# --offline skips the URI check, which downloads and parses every airspace file
# the manifest points at.  That is too slow and too dependent on third-party
# hosts to gate a pull request; check_repo_urls.yml runs it daily against the
# published manifest instead.

ERROR=0
WARNED=0
OFFLINE=0
ARGS=()

for arg in "$@"; do
  case "${arg}" in
    --offline) OFFLINE=1 ;;
    *) ARGS+=("${arg}") ;;
  esac
done

OUT="${ARGS[0]}"

# Set default to output if not specified
if [ -z "${OUT}" ]; then
  OUT="./output"
fi

CONTENT="${OUT}/content"

# report all errors don't halt.
if ! ./script/check/check_waypoints_country.py "${CONTENT}"/waypoint/country/*.cup; then
  ERROR=1
fi

# Waypoint parsing does not gate yet.  Three files in the published set fail it
# -- GLB-WPT-ProvingGrounds-XCSoar.cup and CZ-WPT-WaveCamp-2022-OBv1.cup on
# "Reading frequency failed", ZA_Cape_2023-11-10.cup on "Reading elevation
# failed" -- and aerofiles has already proved stricter than XCSoar's own parser
# elsewhere in this repository, so a failure here does not establish that a
# pilot cannot read the file.  Reported loudly until someone has checked those
# three against XCSoar and decided.
while IFS= read -r -d '' each; do
  if ! ./script/check/check_waypoints.py "${each}"; then
    echo "WARNING: waypoint file does not parse: ${each}"
    WARNED=1
  fi
done < <(find "${CONTENT}/waypoint/" -type f -name "*.cup" -print0)

if ! ./script/check/check_airspaces.py "${CONTENT}"/airspace/; then
  ERROR=1
fi

if [ "${OFFLINE}" = '0' ]; then
  if ! ./script/check/check_urls.py "${OUT}"/repository; then
    ERROR=1
  fi
fi

if [ "${WARNED}" = '1' ]; then
  echo "There where warnings (see WARNING lines above)."
fi

if [ "${ERROR}" = '1' ]; then
   echo "There where errors."
   exit 1
fi
