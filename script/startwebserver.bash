#!/bin/bash

echo "$$"
cd "${2}"
nohup python3 -m http.server "${2}" &
