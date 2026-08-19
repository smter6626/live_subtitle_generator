#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BOOTSTRAP="$ROOT_DIR/scripts/bootstrap_python_env.sh"
WHISPER_BOOTSTRAP="$ROOT_DIR/scripts/bootstrap_whisper_runtime.sh"
RELEASE_BUILD="$ROOT_DIR/scripts/build_macos.sh"
FORMAL_PYTHON="$ROOT_DIR/.venv/bin/python"
APP_PATH="$ROOT_DIR/dist/ClassroomTranscriber.app"
APP_EXECUTABLE="$APP_PATH/Contents/MacOS/ClassroomTranscriber"

log() {
  printf '[build-orchestrator] %s\n' "$*"
}

fail() {
  printf '[build-orchestrator] ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ $# -ne 0 ]]; then
  fail "this build entry does not accept arguments"
fi

[[ "$(uname -s)" == "Darwin" ]] || fail "supported build host OS is macOS"
[[ "$(uname -m)" == "arm64" ]] || fail "supported build host architecture is arm64"

for required_entry in "$PYTHON_BOOTSTRAP" "$WHISPER_BOOTSTRAP" "$RELEASE_BUILD"; do
  [[ -x "$required_entry" ]] || fail "required executable is missing: $required_entry"
done

cd "$ROOT_DIR"

log "prepare formal Python environment"
"$PYTHON_BOOTSTRAP"
[[ -x "$FORMAL_PYTHON" ]] || fail "formal Python was not created: .venv/bin/python"

log "prepare pinned whisper Runtime"
"$WHISPER_BOOTSTRAP"

log "build Release App with .venv/bin/python"
PYTHON="$FORMAL_PYTHON" "$RELEASE_BUILD"

[[ -d "$APP_PATH" ]] || fail "Release App was not generated: dist/ClassroomTranscriber.app"
[[ -d "$APP_PATH/Contents" ]] || fail "Release App Contents directory is missing"
[[ -d "$APP_PATH/Contents/Resources" ]] || fail "Release App Resources directory is missing"
[[ -x "$APP_EXECUTABLE" ]] || fail "Release App main executable is missing"

log "build PASS"
log "App: $APP_PATH"
