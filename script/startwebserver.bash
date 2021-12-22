#!/bin/bash

echo "$$"
cd "${1}"
nohup python3 -m http.server --directory "${2}" "${1}" &
