#!/bin/bash

# Deploy assets created by build.bash to DEPLOY_HOST.

# Required environment variables:
#   DEPLOY_KEY
#   DEPLOY_USER
#   DEPLOY_HOST
#   DEPLOY_PATH
#   DEPLOY_PORT

# Halt on errors:
set -e
# Echo commands:
set -x

if [[ -z ${DEPLOY_KEY} || -z ${DEPLOY_USER} || -z ${DEPLOY_HOST} || -z ${DEPLOY_PATH} || -z ${DEPLOY_PORT} ]]; then
  echo 'One or more variables are undefined. Exiting.'
  exit 1
fi


# SSH identity_file (DO NOT inadvertently rsync to production!)
ID_FILE="ssh_deploy_key"

KH_FILE="known_hosts"

# Protect this private key file:
umask 077
# Hide only this command:
set +x
echo "${DEPLOY_KEY}" > ${ID_FILE}
set -x

ssh-keyscan -p "${DEPLOY_PORT}" "${DEPLOY_HOST}" > ${KH_FILE}

SSH_CMD="ssh -p ${DEPLOY_PORT} -i ${ID_FILE} -o UserKnownHostsFile=${KH_FILE}"

${SSH_CMD} "${DEPLOY_USER}"@"${DEPLOY_HOST}" mkdir -p "${DEPLOY_PATH}"

rsync --delete -avze "${SSH_CMD}" ./waypoints/         "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/waypoints/
rsync --delete -avze "${SSH_CMD}" ./waypoints-special/ "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/waypoints-special/
rsync --delete -avze "${SSH_CMD}" ./airspaces/         "${DEPLOY_USER}"@"${DEPLOY_HOST}":"${DEPLOY_PATH}"/airspaces/

# Cleanup
rm -f ${KH_FILE} ${ID_FILE}
