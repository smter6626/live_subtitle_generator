#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
CONTRACT_HELPER="$ROOT_DIR/scripts/whisper_runtime_contract.py"

log() {
  printf '[whisper-bootstrap] %s\n' "$*"
}

fail() {
  printf '[whisper-bootstrap] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf 'Usage: %s [--verify-only]\n' "${0##*/}"
}

MODE="bootstrap"
case "${1:-}" in
  "") ;;
  --verify-only) MODE="verify" ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    fail "unsupported argument: $1"
    ;;
esac
if [[ $# -gt 1 ]]; then
  usage >&2
  fail "expected at most one argument"
fi

[[ "$(uname -s)" == "Darwin" ]] || fail "supported host OS is macOS"
[[ "$(uname -m)" == "arm64" ]] || fail "supported host architecture is arm64"

check_host_prerequisites() {
  local tool_name
  local clang_path
  for tool_name in git curl tar shasum xcrun clang make file otool; do
    command -v "$tool_name" >/dev/null 2>&1 || \
      fail "required Apple build host tool is missing: $tool_name"
  done
  clang_path="$(xcrun --find clang 2>/dev/null)" || \
    fail "Apple Command Line Tools are unavailable: xcrun cannot find clang"
  [[ -x "$clang_path" ]] || fail "xcrun returned a non-executable clang: $clang_path"
  log "host prerequisites PASS (Apple clang: $clang_path)"
}

check_host_prerequisites
[[ -x "$PYTHON_BIN" ]] || \
  fail "formal Python environment missing; run scripts/bootstrap_python_env.sh first"
[[ -f "$CONTRACT_HELPER" ]] || fail "Runtime contract helper missing"

contract_get() {
  "$PYTHON_BIN" "$CONTRACT_HELPER" get "$1"
}

CMAKE_VERSION="$(contract_get frozen.cmake.exact_version)"
CMAKE_ASSET="$(contract_get frozen.cmake.acquisition.asset)"
CMAKE_ASSET_URL="$(contract_get frozen.cmake.acquisition.asset_url)"
CMAKE_ASSET_SHA256="$(contract_get frozen.cmake.acquisition.asset_sha256)"
CMAKE_INSTALL_REL="$(contract_get frozen.cmake.project_local_install_root_path)"
CMAKE_BINARY_REL="$(contract_get frozen.cmake.binary_path)"
CMAKE_INSTALL_ROOT="$ROOT_DIR/$CMAKE_INSTALL_REL"
CMAKE_BINARY="$ROOT_DIR/$CMAKE_BINARY_REL"

WHISPER_REPOSITORY="$(contract_get frozen.whisper_cpp.repository)"
WHISPER_COMMIT="$(contract_get frozen.whisper_cpp.commit)"
WHISPER_SOURCE_REL="$(contract_get frozen.whisper_cpp.local_rebuild_root_path)"
WHISPER_SOURCE_ROOT="$ROOT_DIR/$WHISPER_SOURCE_REL"
WHISPER_BUILD_ROOT="$WHISPER_SOURCE_ROOT/build"
CMAKE_GENERATOR="$(contract_get frozen.whisper_cpp.build_profile.cmake_generator)"
BUILD_TARGET="$(contract_get frozen.whisper_cpp.build_profile.build_target)"
TARGET_ARCHITECTURE="$(contract_get frozen.whisper_cpp.build_profile.target_architecture)"

cmake_version_matches() {
  [[ -x "$CMAKE_BINARY" ]] && \
    [[ "$("$CMAKE_BINARY" --version | awk 'NR == 1 {print $3}')" == "$CMAKE_VERSION" ]]
}

verify_cmake_existing() {
  [[ -x "$CMAKE_BINARY" ]] || \
    fail "project-local CMake is missing: $CMAKE_BINARY_REL"
  cmake_version_matches || \
    fail "project-local CMake version mismatch; expected $CMAKE_VERSION"
  log "CMake $CMAKE_VERSION verified at $CMAKE_BINARY_REL"
}

ensure_cmake() {
  local cmake_tools_root
  local install_temp
  local archive_path
  local extracted_app
  local binary_suffix
  local staged_binary

  if cmake_version_matches; then
    log "CMake $CMAKE_VERSION ready at $CMAKE_BINARY_REL"
    return
  fi
  if [[ -e "$CMAKE_INSTALL_ROOT" ]]; then
    fail "refusing to overwrite unexpected or invalid managed CMake state: $CMAKE_INSTALL_REL"
  fi

  cmake_tools_root="$(dirname "$CMAKE_INSTALL_ROOT")"
  mkdir -p "$cmake_tools_root"
  install_temp="$(mktemp -d "$cmake_tools_root/.install.XXXXXX")"
  archive_path="$install_temp/$CMAKE_ASSET"

  cleanup_cmake_temp() {
    if [[ -n "$install_temp" && "$install_temp" == "$cmake_tools_root"/.install.* ]]; then
      rm -rf -- "$install_temp"
    fi
  }
  trap cleanup_cmake_temp EXIT

  log "CMake $CMAKE_VERSION download from Kitware official release"
  curl --proto '=https' --tlsv1.2 -fsSL "$CMAKE_ASSET_URL" -o "$archive_path"
  printf '%s  %s\n' "$CMAKE_ASSET_SHA256" "$archive_path" | \
    shasum -a 256 -c - >/dev/null
  log "CMake artifact SHA-256 PASS"

  tar -xzf "$archive_path" -C "$install_temp"
  extracted_app="$install_temp/${CMAKE_ASSET%.tar.gz}/CMake.app"
  [[ -d "$extracted_app" ]] || \
    fail "official CMake archive has an unexpected layout"
  mkdir "$install_temp/install"
  mv "$extracted_app" "$install_temp/install/CMake.app"

  binary_suffix="${CMAKE_BINARY_REL#"$CMAKE_INSTALL_REL"/}"
  [[ "$binary_suffix" != "$CMAKE_BINARY_REL" ]] || \
    fail "CMake binary path is outside its managed install root"
  staged_binary="$install_temp/install/$binary_suffix"
  [[ -x "$staged_binary" ]] || fail "official CMake archive binary is missing"
  [[ "$("$staged_binary" --version | awk 'NR == 1 {print $3}')" == "$CMAKE_VERSION" ]] || \
    fail "downloaded CMake version does not match $CMAKE_VERSION"

  mv "$install_temp/install" "$CMAKE_INSTALL_ROOT"
  cleanup_cmake_temp
  trap - EXIT
  verify_cmake_existing
}

validate_existing_source() {
  local remote
  local source_status
  git -C "$WHISPER_SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
    fail "$WHISPER_SOURCE_REL exists but is not a Git worktree"
  remote="$(git -C "$WHISPER_SOURCE_ROOT" remote get-url origin 2>/dev/null)" || \
    fail "$WHISPER_SOURCE_REL has no origin remote"
  [[ "${remote%/}" == "${WHISPER_REPOSITORY%/}" ]] || \
    fail "unexpected whisper.cpp origin: $remote"
  source_status="$(git -C "$WHISPER_SOURCE_ROOT" status --porcelain --untracked-files=all)"
  [[ -z "$source_status" ]] || \
    fail "whisper.cpp worktree has user changes; refusing to overwrite:\n$source_status"
}

create_pinned_source() {
  local source_parent
  local clone_temp
  source_parent="$(dirname "$WHISPER_SOURCE_ROOT")"
  mkdir -p "$source_parent"
  clone_temp="$(mktemp -d "$source_parent/.whisper-bootstrap.XXXXXX")"

  cleanup_clone_temp() {
    if [[ -n "$clone_temp" && "$clone_temp" == "$source_parent"/.whisper-bootstrap.* ]]; then
      rm -rf -- "$clone_temp"
    fi
  }
  trap cleanup_clone_temp EXIT

  log "whisper.cpp fetch pinned commit $WHISPER_COMMIT"
  git init -q "$clone_temp"
  git -C "$clone_temp" remote add origin "$WHISPER_REPOSITORY"
  git -C "$clone_temp" fetch --depth=1 --no-tags origin "$WHISPER_COMMIT"
  git -C "$clone_temp" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$clone_temp" rev-parse HEAD)" == "$WHISPER_COMMIT" ]] || \
    fail "fetched whisper.cpp commit does not match the Manifest pin"
  [[ ! -e "$WHISPER_SOURCE_ROOT" ]] || \
    fail "$WHISPER_SOURCE_REL appeared while bootstrap was running"
  mv "$clone_temp" "$WHISPER_SOURCE_ROOT"
  trap - EXIT
}

ensure_pinned_source() {
  local source_head
  if [[ -e "$WHISPER_SOURCE_ROOT" ]]; then
    [[ -d "$WHISPER_SOURCE_ROOT" ]] || \
      fail "$WHISPER_SOURCE_REL exists but is not a directory"
    validate_existing_source
    if ! git -C "$WHISPER_SOURCE_ROOT" cat-file -e "$WHISPER_COMMIT^{commit}" 2>/dev/null; then
      log "whisper.cpp fetching required pinned commit"
      git -C "$WHISPER_SOURCE_ROOT" fetch --no-tags origin "$WHISPER_COMMIT"
    fi
    source_head="$(git -C "$WHISPER_SOURCE_ROOT" rev-parse HEAD)"
    if [[ "$source_head" != "$WHISPER_COMMIT" ]] || \
       git -C "$WHISPER_SOURCE_ROOT" symbolic-ref -q HEAD >/dev/null 2>&1; then
      log "whisper.cpp checkout detached pinned commit $WHISPER_COMMIT"
      git -C "$WHISPER_SOURCE_ROOT" checkout -q --detach "$WHISPER_COMMIT"
    fi
  else
    create_pinned_source
  fi
  validate_existing_source
  [[ "$(git -C "$WHISPER_SOURCE_ROOT" rev-parse HEAD)" == "$WHISPER_COMMIT" ]] || \
    fail "whisper.cpp HEAD does not match the Manifest pin"
  if git -C "$WHISPER_SOURCE_ROOT" symbolic-ref -q HEAD >/dev/null 2>&1; then
    fail "whisper.cpp is not detached at the Manifest pin"
  fi
  log "whisper.cpp pinned detached commit ready: $WHISPER_COMMIT"
}

configure_and_build() {
  local cmake_argument_text
  local contract_argument
  local cmake_arguments_array=()

  cmake_argument_text="$("$PYTHON_BIN" "$CONTRACT_HELPER" cmake-arguments)"
  while IFS= read -r contract_argument; do
    [[ -n "$contract_argument" ]] && cmake_arguments_array+=("$contract_argument")
  done <<< "$cmake_argument_text"
  [[ "${#cmake_arguments_array[@]}" -gt 1 ]] || \
    fail "Manifest produced no usable CMake Build Profile"

  log "configure fresh profile (generator: $CMAKE_GENERATOR, architecture: $TARGET_ARCHITECTURE)"
  "$CMAKE_BINARY" --fresh \
    -S "$WHISPER_SOURCE_ROOT" \
    -B "$WHISPER_BUILD_ROOT" \
    -G "$CMAKE_GENERATOR" \
    "${cmake_arguments_array[@]}"

  log "build required target: $BUILD_TARGET"
  "$CMAKE_BINARY" --build "$WHISPER_BUILD_ROOT" \
    --target "$BUILD_TARGET" \
    --parallel \
    --clean-first
}

verify_runtime() {
  verify_cmake_existing
  "$PYTHON_BIN" "$CONTRACT_HELPER" verify-runtime
  log "Runtime verify PASS"
}

cd "$ROOT_DIR"
if [[ "$MODE" == "verify" ]]; then
  log "verify-only (no download, checkout, configure, or compile)"
  verify_runtime
  exit 0
fi

ensure_cmake
ensure_pinned_source
configure_and_build
verify_runtime
log "whisper Runtime bootstrap PASS"
