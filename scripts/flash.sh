#!/usr/bin/env bash
set -euo pipefail

echo "Deprecated: use ./scripts/firmware.sh podman flash" >&2
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/firmware.sh" podman flash
