#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_PATH="dist/ClassroomTranscriber.app"
SPEC_PATH="packaging/ClassroomTranscriber.spec"
DOWNLOAD_SCRIPT="vendor/whisper.cpp/download-ggml-model.sh"
PACKAGE_RUNTIME_HELPER="scripts/package_runtime.py"
PACKAGED_RUNTIME_VERIFIER="scripts/verify_packaged_runtime.py"
APP_ICON_BUILDER="scripts/build_app_icon.py"
RELEASE_IDENTITY_HELPER="scripts/release_identity.py"
BUILD_PROVENANCE_PATH="dist/ClassroomTranscriber.app.provenance.json"
FORMAL_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$FORMAL_PYTHON" ]]; then
  echo "Formal project Python is missing: .venv/bin/python"
  exit 1
fi
if [[ -n "${PYTHON:-}" ]] && ! "$FORMAL_PYTHON" -c \
  'import os, sys; raise SystemExit(0 if os.path.samefile(sys.argv[1], sys.argv[2]) else 1)' \
  "$PYTHON" "$FORMAL_PYTHON"; then
  echo "Formal Release build rejects non-project PYTHON: $PYTHON"
  exit 1
fi
PYTHON_BIN="$FORMAL_PYTHON"
if [[ "$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')" != "3.12.14" ]]; then
  echo "Formal Release build requires Python 3.12.14 from .venv/bin/python"
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
[[ -f "$APP_ICON_BUILDER" ]] || {
  echo "App icon builder not found: $APP_ICON_BUILDER"
  exit 1
}
[[ -f "$RELEASE_IDENTITY_HELPER" ]] || {
  echo "Release identity helper not found: $RELEASE_IDENTITY_HELPER"
  exit 1
}
for required_tool in file otool install_name_tool codesign iconutil; do
  command -v "$required_tool" >/dev/null 2>&1 || {
    echo "Required macOS packaging tool not found: $required_tool"
    exit 1
  }
done

echo "Validating clean canonical source identity..."
SOURCE_COMMIT="$("$PYTHON_BIN" "$RELEASE_IDENTITY_HELPER" check-clean-source)"

echo "Validating required Manifest Runtime sources..."
"$PYTHON_BIN" "$PACKAGE_RUNTIME_HELPER" validate-sources

echo "Cleaning old build artifacts..."
rm -rf build dist

echo "Generating repository-owned macOS App icon..."
"$PYTHON_BIN" "$APP_ICON_BUILDER"

echo "Building ClassroomTranscriber.app with PyInstaller..."
"$PYTHON_BIN" -m PyInstaller "$SPEC_PATH" --noconfirm --clean --log-level WARN
echo "PyInstaller build PASS"

echo "Normalizing packaged Runtime install names and RPaths..."
"$PYTHON_BIN" "$PACKAGE_RUNTIME_HELPER" normalize-app "$APP_PATH"

echo "Applying required ad-hoc codesign after Runtime normalization..."
codesign --force --deep --sign - "$APP_PATH"

echo "Verifying final packaged Runtime..."
"$PYTHON_BIN" "$PACKAGED_RUNTIME_VERIFIER" "$APP_PATH"

echo "Writing canonical non-clobbering build provenance..."
"$PYTHON_BIN" "$RELEASE_IDENTITY_HELPER" write-build-provenance \
  --app "$APP_PATH" \
  --output "$BUILD_PROVENANCE_PATH" \
  --source-commit "$SOURCE_COMMIT"
echo "Build provenance: $BUILD_PROVENANCE_PATH"

echo
echo "Build complete:"
echo "  $APP_PATH"
echo
echo "Manual test:"
echo "  open \"$APP_PATH\""
echo "  In the app, open Manage Models, select or download a model, then Start/Stop Recording."
