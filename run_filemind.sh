#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

if [ -x "dist/FileMind" ]; then
    exec "./dist/FileMind"
elif [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" -m filemind.gui.app
elif command -v python3 >/dev/null 2>&1; then
    exec python3 -m filemind.gui.app
else
    echo "Python 3 is required to run FileMind." >&2
    exit 1
fi
