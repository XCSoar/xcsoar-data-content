#!/bin/bash

if [ -z "${1}" ]; then
  echo "Usage: specify output directory"
  exit 1
fi

OUT="${1}"

# Build maps for xcsoar
MAPGEN_TMPDIR="$(mktemp -d -p "${PWD}" )"
mkdir -p "${MAPGEN_TMPDIR}/data"
docker run -u "$(id -u "${USER}")":"$(id -g "${USER}")" --mount type=bind,source="${MAPGEN_TMPDIR}"/data,target=/opt/mapgen/data --entrypoint "/opt/mapgen/bin/generate-maps" -w "/opt/mapgen/data" "ghcr.io/xcsoar/mapgen-worker"
mkdir -p "${OUT}"
rsync -aptv "${MAPGEN_TMPDIR}"/data/*.xcm "${OUT}"
rm -rf "${MAPGEN_TMPDIR}"
