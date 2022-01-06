#!/bin/bash

# Build maps for xcsoar
# Try to only build the ones that are changed

if [ -z "${1}" ]; then
  echo "Usage: specify output directory"
  exit 1
fi

OUT="${1}"

MAPGEN_TMPDIR="$(mktemp -d -p "${PWD}" )"
mkdir -p "${MAPGEN_TMPDIR}/data"

REMOTE_NAME="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)"

# Ensure we compare to the master branch on github
git remote add "${REMOTE_NAME}" https://github.com/XCSoar/xcsoar-data-content.git
git fetch "${REMOTE_NAME}"

MAPS_NEW=$(git diff --name-status master | grep 'data/source/map' | grep ^A | cut -f2) 
MAPS_MVE=$(git diff --name-status master | grep 'data/source/map' | grep ^R100 | cut -f2)
MAPS_MOD=$(git diff --name-status master | grep 'data/source/map' | grep ^M | cut -f2)
#MAPS_DEL=$(git diff --name-status master | grep 'data/source/map' | grep ^D | cut -f2)

git remote remove "${REMOTE_NAME}"

# Check if any maps have been modified, else exit
if [ -z "${MAPS_NEW}${MAPS_MVE}${MAPS_MOD}" ]; then
  exit 0
fi

if ! type docker > /dev/null
then
  echo "Building maps requires docker or podman installed" 
  exit 1
fi

# delete remote file with rsync
#rsync -rv --delete --include=foo.txt '--exclude=*' /home/user/ user@remote:/home/user/
# Run the docker container for every file changed in git
echo "${MAPS}"

for MAP in ${MAPS_NEW} ${MAPS_MOD} ${MAPS_MVE}
  do
     # Copy the map json to the workdir
     MAPDIR=$(dirname "${MAP}")
     mkdir -p "${MAPGEN_TMPDIR}"/"${MAPDIR}"
     cp "${MAP}" "${MAPGEN_TMPDIR}"/"${MAP}"

     # Generate map with container
     docker run -u "$(id -u "${USER}")":"$(id -g "${USER}")" \
       --mount type=bind,source="${MAPGEN_TMPDIR}"/data,target=/opt/mapgen/data \
       -w "/opt/mapgen/data" --entrypoint /opt/mapgen/bin/generate-map-from-json \
       "ghcr.io/xcsoar/mapgen-worker" /opt/mapgen/"${MAP}" > /dev/null

     # strip data from path
     MAPDIR=$(echo "${MAPDIR}" | cut -f2- -d'/')

     # Copy the map to the output directory
     mkdir -p "${OUT}"/"${MAPDIR}"
     cp  "${MAPGEN_TMPDIR}"/data/*.xcm "${OUT}"/"${MAPDIR}"
done

# Cleanup 
rm -rf "${MAPGEN_TMPDIR}"
