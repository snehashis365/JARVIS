#!/usr/bin/env bash
# Jarvis Automated Test Runner
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

export COVERAGE_FILE="/tmp/.coverage_jarvis"

echo "=== Running Jarvis Test Suite ==="
.venv/bin/pytest tests/ --cov=jarvis --cov-report=term-missing "$@"
