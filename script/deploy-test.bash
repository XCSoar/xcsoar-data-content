#!/bin/bash

# Do a test deployment, for local modification and PR testing

# Echo commands:
set -x

# Output Directory for build process
BUILD_DIR="$(mktemp -d)"
TEST_DIR="$(mktemp -d)"

# Build repository and content
./script/build/build.bash "${BUILD_DIR}"

# Do deploy to test directory
rsync -aptv "${BUILD_DIR}"/ "${TEST_DIR}"/

# Replace URL of download.xcsoar.org with localhost for testing local resources
sed -i 's/https:\/\/download.xcsoar.org/http:\/\/localhost:8585/' "${TEST_DIR}"/repository

# Start temporary webserver running in directory
./script/startwebserver.bash 8585 "${TEST_DIR}" > "${TEST_DIR}"/webserver.pid

# Run Check script for urls on localhost
script/check/check_urls.py http://localhost:8585/repository

# Stop webserver from pidfile
pkill "cat ${TEST_DIR}/webserver.pid"

# Cleanup
rm -rf "${BUILD_DIR}" "${TEST_DIR}"
