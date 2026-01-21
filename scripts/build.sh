#!/usr/bin/env bash
set -euo pipefail

echo "Deprecated: use ./scripts/firmware.sh podman build" >&2
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/firmware.sh" podman build
