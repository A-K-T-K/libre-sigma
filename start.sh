#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if command -v python3 >/dev/null 2>&1; then
    python3 start.py "$@"
elif command -v python >/dev/null 2>&1; then
    python start.py "$@"
else
    echo "[LibRE Sigma Error] Python 3 was not found."
    echo "Please install Python 3.10+ to run LibRE Sigma."
    exit 1
fi
