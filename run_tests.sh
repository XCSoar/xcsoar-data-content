#!/bin/bash
# Run the repository tests
cd "$(dirname "$0")"
python3 -m pytest tests/test_repository.py -v