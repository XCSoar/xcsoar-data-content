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

# Description-only JSON edits must not rebuild .xcm files.
filter_maps_mod_bbox() {
  local ref="$1"
  local -a maps_mod
  # Word-split the space-separated path list into argv.
  read -r -a maps_mod <<< "${MAPS_MOD}"
  MAPS_MOD=$(python3 - "$ref" "${maps_mod[@]}" <<'PY'
import json, subprocess, sys
ref = sys.argv[1]
keep = []
for path in sys.argv[2:]:
    new = json.load(open(path, encoding="utf-8"))
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        keep.append(path)
        continue
    old = json.loads(proc.stdout)
    if old.get("bounding_box") != new.get("bounding_box"):
        keep.append(path)
print(" ".join(keep))
PY
)
}

if [ "${BUILD_MAPS}" == "true" ]; then
  MAPS_NEW=$(find ./data/source/map/ -type f -iname "*.json")

else

  REMOTE_NAME="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)"

  MAP_DIFF_REF=""
  if [[ -n "${PREVIOUS_COMMIT}" || -n "${PREVIOUS_COMMIT_PR}" ]]; then
      if [ -n "${PREVIOUS_COMMIT}" ]; then
        MAP_DIFF_REF="${PREVIOUS_COMMIT}"
        MAPS_NEW=$(git diff --name-status "${PREVIOUS_COMMIT}" | grep 'data/source/map' | grep ^A | cut -f2)
        MAPS_MVE=$(git diff --name-status "${PREVIOUS_COMMIT}" | grep 'data/source/map' | grep ^R100 | cut -f2)
        MAPS_MOD=$(git diff --name-status "${PREVIOUS_COMMIT}" | grep 'data/source/map' | grep ^M | cut -f2)
      fi

      if [ -n "${PREVIOUS_COMMIT_PR}" ]; then
        MAP_DIFF_REF="${PREVIOUS_COMMIT_PR}"
        MAPS_NEW=$(git diff --name-status "${PREVIOUS_COMMIT_PR}" | grep 'data/source/map' | grep ^A | cut -f2)
        MAPS_MVE=$(git diff --name-status "${PREVIOUS_COMMIT_PR}" | grep 'data/source/map' | grep ^R100 | cut -f2)
        MAPS_MOD=$(git diff --name-status "${PREVIOUS_COMMIT_PR}" | grep 'data/source/map' | grep ^M | cut -f2)
      fi
  else
  # Ensure we compare to the master branch on github
  git remote add "${REMOTE_NAME}" https://github.com/XCSoar/xcsoar-data-content.git
  git fetch "${REMOTE_NAME}"

  MAP_DIFF_REF="$(git rev-parse "${REMOTE_NAME}/master")"
  MAPS_NEW=$(git diff --name-status "${REMOTE_NAME}"/master | grep 'data/source/map' | grep ^A | cut -f2)
  MAPS_MVE=$(git diff --name-status "${REMOTE_NAME}"/master | grep 'data/source/map' | grep ^R100 | cut -f2)
  MAPS_MOD=$(git diff --name-status "${REMOTE_NAME}"/master | grep 'data/source/map' | grep ^M | cut -f2)
  _MAPS_DEL=$(git diff --name-status "${REMOTE_NAME}"/master | grep 'data/source/map' | grep ^D | cut -f2)

  git remote remove "${REMOTE_NAME}"
  fi

  if [ -n "${MAP_DIFF_REF}" ] && [ -n "${MAPS_MOD}" ]; then
    filter_maps_mod_bbox "${MAP_DIFF_REF}"
  fi

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

fi

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
     MAPDIR=$(echo "${MAPDIR}" | cut -f3- -d'/')

     # Copy the map to the output directory
     mkdir -p "${OUT}"/source/"${MAPDIR}"
     cp  "${MAPGEN_TMPDIR}"/data/*.xcm "${OUT}"/source/"${MAPDIR}"
done

# Cleanup
rm -rf "${MAPGEN_TMPDIR}"
