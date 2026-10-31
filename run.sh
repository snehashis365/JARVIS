#!/usr/bin/env bash
# Jarvis Assistant Launch Script
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment .venv not found. Please initialize .venv first."
    exit 1
fi

export PYTHONUNBUFFERED=1

echo "Starting Jarvis Assistant..."
exec .venv/bin/python -m jarvis.cli start "$@"
