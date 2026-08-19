#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_PATH="dist/ClassroomTranscriber.app"
SPEC_PATH="packaging/ClassroomTranscriber.spec"
DOWNLOAD_SCRIPT="vendor/whisper.cpp/download-ggml-model.sh"
PACKAGE_RUNTIME_HELPER="scripts/package_runtime.py"
PACKAGED_RUNTIME_VERIFIER="scripts/verify_packaged_runtime.py"

python_exists() {
  [[ -x "$1" ]] || command -v "$1" >/dev/null 2>&1
}

candidate_has_build_deps() {
  "$1" -c "import PyInstaller; import PySide6" >/dev/null 2>&1
}

PYTHON_CANDIDATES=()
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_CANDIDATES+=("$PYTHON")
else
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    PYTHON_CANDIDATES+=("$VIRTUAL_ENV/bin/python")
  fi
  if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
    PYTHON_CANDIDATES+=("$ROOT_DIR/venv/bin/python")
  fi
  PYTHON_CANDIDATES+=("python3")
fi

PYTHON_BIN=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
  if python_exists "$candidate" && candidate_has_build_deps "$candidate"; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in "${PYTHON_CANDIDATES[@]}"; do
    if python_exists "$candidate"; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "No usable Python interpreter found."
  exit 1
fi

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is not installed."
  echo "Install it with: $PYTHON_BIN -m pip install pyinstaller"
  exit 1
fi

if ! "$PYTHON_BIN" -c "import PySide6" >/dev/null 2>&1; then
  echo "PySide6 is not installed in the build interpreter."
  echo "Install it with: $PYTHON_BIN -m pip install PySide6"
  exit 1
fi

echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" -c "import sys, PyInstaller, PySide6; from PySide6.QtCore import qVersion; print('Python:', sys.version.replace(chr(10), ' ')); print('PyInstaller:', PyInstaller.__version__); print('PySide6:', PySide6.__version__); print('Qt:', qVersion())"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Spec file not found: $SPEC_PATH"
  exit 1
fi

if [[ ! -f "$DOWNLOAD_SCRIPT" ]]; then
  echo "Required model download script not found: $DOWNLOAD_SCRIPT"
  exit 1
fi

if [[ ! -r "$DOWNLOAD_SCRIPT" ]]; then
  echo "Required model download script is not readable: $DOWNLOAD_SCRIPT"
  exit 1
fi

if ! sh -n "$DOWNLOAD_SCRIPT"; then
  echo "Required model download script has invalid shell syntax: $DOWNLOAD_SCRIPT"
  exit 1
fi

[[ -f "$PACKAGE_RUNTIME_HELPER" ]] || {
  echo "Packaging Runtime helper not found: $PACKAGE_RUNTIME_HELPER"
  exit 1
}
[[ -f "$PACKAGED_RUNTIME_VERIFIER" ]] || {
  echo "Packaged Runtime verifier not found: $PACKAGED_RUNTIME_VERIFIER"
  exit 1
}
for required_tool in file otool install_name_tool codesign; do
  command -v "$required_tool" >/dev/null 2>&1 || {
    echo "Required macOS packaging tool not found: $required_tool"
    exit 1
  }
done

echo "Validating required Manifest Runtime sources..."
"$PYTHON_BIN" "$PACKAGE_RUNTIME_HELPER" validate-sources

echo "Cleaning old build artifacts..."
rm -rf build dist

echo "Building ClassroomTranscriber.app with PyInstaller..."
"$PYTHON_BIN" -m PyInstaller "$SPEC_PATH" --noconfirm --clean --log-level WARN
echo "PyInstaller build PASS"

echo "Normalizing packaged Runtime install names and RPaths..."
"$PYTHON_BIN" "$PACKAGE_RUNTIME_HELPER" normalize-app "$APP_PATH"

echo "Applying required ad-hoc codesign after Runtime normalization..."
codesign --force --deep --sign - "$APP_PATH"

echo "Verifying final packaged Runtime..."
"$PYTHON_BIN" "$PACKAGED_RUNTIME_VERIFIER" "$APP_PATH"

echo
echo "Build complete:"
echo "  $APP_PATH"
echo
echo "Manual test:"
echo "  open \"$APP_PATH\""
echo "  In the app, open Manage Models, select or download a model, then Start/Stop Recording."
