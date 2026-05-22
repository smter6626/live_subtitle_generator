#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Removing PyInstaller build artifacts..."
rm -rf build dist

echo "Removing Python bytecode caches..."
find . \
  -path "./venv" -prune -o \
  -path "./external/whisper.cpp" -prune -o \
  -path "./models" -prune -o \
  -path "./outputs" -prune -o \
  -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

find . \
  -path "./venv" -prune -o \
  -path "./external/whisper.cpp" -prune -o \
  -path "./models" -prune -o \
  -path "./outputs" -prune -o \
  -type f -name "*.pyc" -delete

echo "Clean complete. Preserved models/, outputs/, external/whisper.cpp/, and venv/."
