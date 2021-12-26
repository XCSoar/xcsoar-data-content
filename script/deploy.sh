#!/bin/bash

# Deploy assets created by build.bash to DEPLOY_HOST.

# Required environment variables:
#   DEPLOY_KEY
#   DEPLOY_USER
#   DEPLOY_HOST
#   DEPLOY_PATH
#   DEPLOY_PORT

# Echo commands:
set -x

# Deploy Variable check
if [[ -z "${DEPLOY_KEY}" || -z "${DEPLOY_USER}" || -z "${DEPLOY_HOST}" || -z "${DEPLOY_PATH}" || -z "${DEPLOY_PORT}" ]]; then
  echo 'One or more variables are undefined. Exiting.'
  exit 1
fi

# Output Directory for build process
BUILD_DIR="$(mktemp -d)"

# SSH identity_file (DO NOT inadvertently rsync to production!)
ID_FILE="$(mktemp)"
KH_FILE="$(mktemp)"

# SSH cmdline
SSH_CMD="ssh -p ${DEPLOY_PORT} -i ${ID_FILE} -o UserKnownHostsFile=${KH_FILE}"

# Build the "repository" file and other website artefacts:
./script/build/build.sh "${BUILD_DIR}"

# Protect this private key file:
umask 077
# Hide only this command:
set +x
echo "${DEPLOY_KEY}" > "${ID_FILE}"
set -x

ssh-keyscan -p "${DEPLOY_PORT}" "${DEPLOY_HOST}" > "${KH_FILE}"
# Rsync content across (waypoint, airspace, etc.). The path matches that in script/build/repository.py's URL.
rsync --delete -avze "${SSH_CMD}" ./data/content/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/content

# NB: Maps need to be generated & deployed by mapgen repo.

# Rsync the "repository" file and other website artefacts to the web root (NB: no --delete!):
rsync -avze "${SSH_CMD}" "${BUILD_DIR}"/repository "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/repository
rsync -avze "${SSH_CMD}" "${BUILD_DIR}"/airspaces/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/airspaces/
rsync -avze "${SSH_CMD}" "${BUILD_DIR}"/waypoints/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/waypoints/

# In any case remove ssh id/kh and build artifacts
rm -rf "${KH_FILE}" "${ID_FILE}" "${BUILD_DIR}"
