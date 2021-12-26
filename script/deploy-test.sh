#!/bin/bash

# Do a test deployment, for local modification and PR testing

# Echo commands:
set -x

# Output Directory for build process
BUILD_DIR="$(mktemp -d)"
TEST_DIR="$(mktemp -d)"

# Functions
function cleanup {
  rm -rf "${BUILD_DIR}" "${TEST_DIR}"
}

# Build repository and content
./script/build/build.sh "${BUILD_DIR}"

# Do deploy to test directory
rsync -aptv "${BUILD_DIR}"/ "${TEST_DIR}"/
rsync -aptv "${BUILD_DIR}"/airspaces/ "${TEST_DIR}"/airspaces/
rsync -aptv ./data/content/ "${TEST_DIR}"/content

# Replace URL of download.xcsoar.org with localhost for testing local resources
sed -i 's/https:\/\/download.xcsoar.org/http:\/\/localhost:8585/' "${TEST_DIR}"/repository
sed -i 's/http:\/\/download.xcsoar.org/http:\/\/localhost:8585/'  "${TEST_DIR}"/repository

# Start temporary webserver running in directory
./script/startwebserver.sh 8585 "${TEST_DIR}" > "${TEST_DIR}"/webserver.pid

# Run Check script for urls on localhost
if ! script/check/check_urls.py http://localhost:8585/repository; then
  echo 'URL Check failed!'
  #cleanup
  exit 1
else
  # Stop webserver from pidfile
  pkill "cat ${TEST_DIR}/webserver.pid"
  #cleanup
fi
