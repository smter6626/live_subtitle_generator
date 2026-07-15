#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_PATH="dist/ClassroomTranscriber.app"
SPEC_PATH="packaging/ClassroomTranscriber.spec"
DOWNLOAD_SCRIPT="vendor/whisper.cpp/download-ggml-model.sh"

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

if [[ ! -x "external/whisper.cpp/build/bin/whisper-cli" ]]; then
  echo "Warning: whisper-cli was not found or is not executable."
  echo "Expected: external/whisper.cpp/build/bin/whisper-cli"
  echo "The app will still build, but packaged whisper-cli may be missing."
fi

echo "Cleaning old build artifacts..."
rm -rf build dist

echo "Building ClassroomTranscriber.app with PyInstaller..."
"$PYTHON_BIN" -m PyInstaller "$SPEC_PATH" --noconfirm --clean

BIN_DIR="$APP_PATH/Contents/Resources/bin"
BUNDLED_DOWNLOAD_SCRIPT="$BIN_DIR/download-ggml-model.sh"
if [[ ! -f "$BUNDLED_DOWNLOAD_SCRIPT" ]]; then
  echo "Packaged model download script not found: $BUNDLED_DOWNLOAD_SCRIPT"
  exit 1
fi
chmod +x "$BUNDLED_DOWNLOAD_SCRIPT"

if [[ -d "$BIN_DIR" ]]; then
  chmod +x "$BIN_DIR/whisper-cli" 2>/dev/null || true

  if [[ -x "$BIN_DIR/whisper-cli" ]]; then
    install_name_tool -add_rpath "@executable_path" "$BIN_DIR/whisper-cli" 2>/dev/null || true
  fi

  for dylib in "$BIN_DIR"/*.dylib; do
    [[ -e "$dylib" ]] || continue
    install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true
  done
fi

if command -v codesign >/dev/null 2>&1 && [[ -d "$APP_PATH" ]]; then
  echo "Applying ad-hoc codesign..."
  codesign --force --deep --sign - "$APP_PATH" || {
    echo "Warning: ad-hoc codesign failed. The app was still built at $APP_PATH"
  }
fi

echo
echo "Build complete:"
echo "  $APP_PATH"
echo
echo "Manual test:"
echo "  open \"$APP_PATH\""
echo "  In the app, open Manage Models, select or download a model, then Start/Stop Recording."
