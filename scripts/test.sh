#!/usr/bin/env bash
set -euo pipefail

echo "Running tests..."
python -m unittest discover -s tests
echo "All tests passed"
