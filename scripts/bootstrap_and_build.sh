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

# C1 uses only inherited pipes. Ordinary Finder/developer calls need no pipe.
# The lifetime pipe has a separate reader so parent death also stops an active
# child, rather than waiting for the next checkpoint. The controller launches
# this invocation in a dedicated process group.
CONTROLLED=0
GUARD_PID=""
CHILD_PID=""
if [[ -n "${REL1C_EVENT_FD:-}${REL1C_ACK_FD:-}${REL1C_LIFETIME_FD:-}" ]]; then
  for descriptor in "${REL1C_EVENT_FD:-}" "${REL1C_ACK_FD:-}" "${REL1C_LIFETIME_FD:-}"; do
    [[ "$descriptor" =~ ^[0-9]+$ && "$descriptor" -ge 3 ]] || fail "invalid control pipe"
    [[ -p /dev/fd/"$descriptor" ]] || fail "missing control pipe"
  done
  [[ "$REL1C_EVENT_FD" != "$REL1C_ACK_FD" && "$REL1C_EVENT_FD" != "$REL1C_LIFETIME_FD" &&
     "$REL1C_ACK_FD" != "$REL1C_LIFETIME_FD" ]] || fail "invalid control pipe"
  CONTROLLED=1
  (
    IFS= read -r ignored <&"$REL1C_LIFETIME_FD" || true
    kill -KILL -- "-$$" 2>/dev/null || kill -KILL "$$" 2>/dev/null || true
  ) &
  GUARD_PID=$!
  controlled_cleanup() {
    trap - EXIT TERM INT HUP
    if [[ -n "$CHILD_PID" ]]; then
      kill -KILL "$CHILD_PID" 2>/dev/null || true
      wait "$CHILD_PID" 2>/dev/null || true
    fi
    kill -TERM "$GUARD_PID" 2>/dev/null || true
    wait "$GUARD_PID" 2>/dev/null || true
  }
  trap controlled_cleanup EXIT
  trap 'exit 1' TERM INT HUP
fi

checkpoint() {
  [[ "$CONTROLLED" -eq 1 ]] || return 0
  local event="$1"
  local answer=""
  printf '%s\n' "$event" >&"$REL1C_EVENT_FD" || fail "control pipe closed"
  IFS= read -r -t 30 answer <&"$REL1C_ACK_FD" || fail "control acknowledgement missing"
  [[ "$answer" == "allow:$event" ]] || fail "control denied"
}

controlled_child() {
  "$@" &
  CHILD_PID=$!
  local outcome=0
  wait "$CHILD_PID" || outcome=$?
  CHILD_PID=""
  return "$outcome"
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
checkpoint before:python
if [[ "$CONTROLLED" -eq 1 ]]; then
  controlled_child "$PYTHON_BOOTSTRAP"
else
"$PYTHON_BOOTSTRAP"
fi
checkpoint after:python
[[ -x "$FORMAL_PYTHON" ]] || fail "formal Python was not created: .venv/bin/python"

log "prepare pinned whisper Runtime"
checkpoint before:runtime
if [[ "$CONTROLLED" -eq 1 ]]; then
  controlled_child "$WHISPER_BOOTSTRAP"
else
"$WHISPER_BOOTSTRAP"
fi
checkpoint after:runtime

log "build Release App with .venv/bin/python"
checkpoint before:app
if [[ "$CONTROLLED" -eq 1 ]]; then
  PYTHON="$FORMAL_PYTHON" controlled_child "$RELEASE_BUILD"
else
PYTHON="$FORMAL_PYTHON" "$RELEASE_BUILD"
fi
checkpoint after:app

[[ -d "$APP_PATH" ]] || fail "Release App was not generated: dist/ClassroomTranscriber.app"
[[ -d "$APP_PATH/Contents" ]] || fail "Release App Contents directory is missing"
[[ -d "$APP_PATH/Contents/Resources" ]] || fail "Release App Resources directory is missing"
[[ -x "$APP_EXECUTABLE" ]] || fail "Release App main executable is missing"

log "build PASS"
log "App: $APP_PATH"
