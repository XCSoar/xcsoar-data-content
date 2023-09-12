#!/bin/bash

# halt on errors
set -e

# Deploy assets created by build.sh to DEPLOY_HOST.

# Required environment variables:
#   DEPLOY_KEY
#   DEPLOY_USER
#   DEPLOY_HOST
#   DEPLOY_PATH
#   DEPLOY_PORT

# Set default to output if not specified
if [ -z "${OUT}" ]; then
  OUT="./output"
fi

# Deploy Variable check
if [[ -z "${DEPLOY_KEY}" || -z "${DEPLOY_USER}" || -z "${DEPLOY_HOST}" || -z "${DEPLOY_PATH}" || -z "${DEPLOY_PORT}" ]]; then
  echo 'One or more variables are undefined. Exiting.'
  exit 1
fi

# Output Directory for build process
BUILD_DIR="${OUT}"

# SSH identity_file (DO NOT inadvertently rsync to production!)
ID_FILE="$(mktemp)"
KH_FILE="$(mktemp)"

# SSH cmdline
SSH_CMD="ssh -p ${DEPLOY_PORT} -i ${ID_FILE} -o UserKnownHostsFile=${KH_FILE}"

# Protect this private key file:
umask 077
# Hide only this command:
set +x
echo "${DEPLOY_KEY}" > "${ID_FILE}"
set -x

ssh-keyscan -p "${DEPLOY_PORT}" "${DEPLOY_HOST}" > "${KH_FILE}"

# Rsync the "repository" file and map to the web root (NB: no --delete!):
rsync -avze "${SSH_CMD}" "${BUILD_DIR}"/repository "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/repository
rsync -avze "${SSH_CMD}" "${BUILD_DIR}"/source/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/source/

# the following dir is fully managed by this repo, hence --delete
rsync -avze "${SSH_CMD}" --delete "${BUILD_DIR}"/content/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/content/

# In any case remove ssh id/kh and build artifacts
rm -rf "${KH_FILE}" "${ID_FILE}" "${BUILD_DIR}"
