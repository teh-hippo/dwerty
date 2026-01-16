#!/usr/bin/env bash
# Backward compatibility wrapper for build.sh --podman
# This script is deprecated. Use: ./scripts/build.sh --podman

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build.sh" --podman
