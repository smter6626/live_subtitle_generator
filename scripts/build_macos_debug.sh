#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DIR="dist/ClassroomTranscriberDebug"
SPEC_PATH="packaging/ClassroomTranscriberDebug.spec"

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
  echo "No Python interpreter with both PyInstaller and PySide6 was found."
  echo "Install build dependencies into the Python used for source runs:"
  echo "  python -m pip install pyinstaller PySide6"
  exit 1
fi

echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" -c "import sys, PyInstaller, PySide6; from PySide6.QtCore import qVersion; print('Python:', sys.version.replace(chr(10), ' ')); print('PyInstaller:', PyInstaller.__version__); print('PySide6:', PySide6.__version__); print('Qt:', qVersion())"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Spec file not found: $SPEC_PATH"
  exit 1
fi

echo "Cleaning old debug build artifacts..."
rm -rf build/ClassroomTranscriberDebug "$APP_DIR"

echo "Building console debug app with PyInstaller..."
"$PYTHON_BIN" -m PyInstaller "$SPEC_PATH" --noconfirm --clean

BIN_DIR="$APP_DIR/bin"
if [[ -d "$BIN_DIR" ]]; then
  chmod +x "$BIN_DIR/whisper-cli" 2>/dev/null || true
  chmod +x "$BIN_DIR/download-ggml-model.sh" 2>/dev/null || true

  if [[ -x "$BIN_DIR/whisper-cli" ]]; then
    install_name_tool -add_rpath "@executable_path" "$BIN_DIR/whisper-cli" 2>/dev/null || true
  fi

  for dylib in "$BIN_DIR"/*.dylib; do
    [[ -e "$dylib" ]] || continue
    install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true
  done
fi

echo
echo "Debug build complete:"
echo "  $APP_DIR/ClassroomTranscriberDebug"
echo
echo "Run from Terminal to see stdout/stderr:"
echo "  ./dist/ClassroomTranscriberDebug/ClassroomTranscriberDebug"
echo
echo "Crash debug log:"
echo "  ~/Library/Application\\ Support/ClassroomTranscriber/logs/crash_debug.log"
