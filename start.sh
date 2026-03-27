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

# Ensure Python can write Unicode characters to the terminal.
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer python3 but fall back to python if only that is available.
if command -v python3 &>/dev/null; then
    exec python3 "${SCRIPT_DIR}/src/OTS_Federation_CLI.py" "$@"
elif command -v python &>/dev/null; then
    exec python "${SCRIPT_DIR}/src/OTS_Federation_CLI.py" "$@"
else
    echo "ERROR: Python 3 is not installed or not found on PATH." >&2
    exit 1
fi
