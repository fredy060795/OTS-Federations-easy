#!/usr/bin/env bash
# start.sh – Launch the OTS Federation Setup Helper (Terminal / CLI)
#
# This script runs the pure terminal interface that works over SSH
# and in any console environment — no graphical display required.
#
# Usage:
#     ./start.sh
#     bash start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "${SCRIPT_DIR}/src/OTS_Federation_CLI.py" "$@"
