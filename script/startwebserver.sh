#!/bin/bash

echo "$$"
cd "${2}"
nohup python3 -m http.server --directory "${2}" "${1}" &
