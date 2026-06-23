#!/usr/bin/env bash
set -euo pipefail

# Run from the max/ project root regardless of the caller's working directory.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Running tests..."
python -m unittest discover -s tests
echo "All tests passed"
