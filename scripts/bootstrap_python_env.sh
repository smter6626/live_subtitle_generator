#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
UV_VERSION="0.12.5"
UV_ASSET="uv-aarch64-apple-darwin.tar.gz"
UV_ASSET_SHA256="5bb0e5fe008a773c3dbcb97ff79cd89e1241464fe9d2f986d52ad8f1b037bd62"
UV_RELEASE_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION"
UV_INSTALL_DIR="$TOOLS_DIR/uv/$UV_VERSION"
UV_BIN="$UV_INSTALL_DIR/uv"
PYTHON_VERSION="3.12.14"
PYTHON_INSTALL_DIR="$TOOLS_DIR/python"
UV_CACHE_DIR="$TOOLS_DIR/cache"
VENV_DIR="$ROOT_DIR/.venv"

log() {
  printf '[python-bootstrap] %s\n' "$*"
}

fail() {
  printf '[python-bootstrap] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf 'Usage: %s [--recreate]\n' "${0##*/}"
}

RECREATE=0
case "${1:-}" in
  "") ;;
  --recreate) RECREATE=1 ;;
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

for required_file in pyproject.toml uv.lock .python-version testCodes/test_python_environment.py; do
  [[ -f "$ROOT_DIR/$required_file" ]] || fail "required contract file missing: $required_file"
done

[[ "$(tr -d '[:space:]' < "$ROOT_DIR/.python-version")" == "$PYTHON_VERSION" ]] || \
  fail ".python-version does not match bootstrap Python $PYTHON_VERSION"

mkdir -p "$TOOLS_DIR" "$UV_INSTALL_DIR" "$PYTHON_INSTALL_DIR" "$UV_CACHE_DIR"

uv_version_matches() {
  [[ -x "$UV_BIN" ]] && [[ "$("$UV_BIN" --version | awk '{print $2}')" == "$UV_VERSION" ]]
}

install_uv() {
  command -v curl >/dev/null 2>&1 || fail "curl is required to download official uv"
  command -v shasum >/dev/null 2>&1 || fail "shasum is required to verify official uv"
  command -v tar >/dev/null 2>&1 || fail "tar is required to unpack official uv"

  local install_temp
  local archive_path
  local extracted_uv
  install_temp="$(mktemp -d "$TOOLS_DIR/.uv-install.XXXXXX")"
  archive_path="$install_temp/$UV_ASSET"

  cleanup_install_temp() {
    if [[ -n "$install_temp" && "$install_temp" == "$TOOLS_DIR"/.uv-install.* ]]; then
      rm -rf -- "$install_temp"
    fi
  }
  trap cleanup_install_temp EXIT

  log "uv download $UV_VERSION from Astral's official GitHub release"
  curl --proto '=https' --tlsv1.2 -fsSL "$UV_RELEASE_URL/$UV_ASSET" -o "$archive_path"
  printf '%s  %s\n' "$UV_ASSET_SHA256" "$archive_path" | shasum -a 256 -c - >/dev/null

  tar -xzf "$archive_path" -C "$install_temp"
  extracted_uv="$install_temp/uv-aarch64-apple-darwin/uv"
  [[ -x "$extracted_uv" ]] || fail "official uv archive did not contain the expected arm64 binary"
  install -m 0755 "$extracted_uv" "$UV_BIN"

  cleanup_install_temp
  trap - EXIT
}

if ! uv_version_matches; then
  install_uv
fi
uv_version_matches || fail "uv version verification failed; expected $UV_VERSION"
log "uv $UV_VERSION ready at .tools/uv/$UV_VERSION/uv"

if [[ "$RECREATE" -eq 1 && -e "$VENV_DIR" ]]; then
  [[ "$VENV_DIR" == "$ROOT_DIR/.venv" ]] || fail "refusing to remove unexpected environment path"
  log "removing project .venv for a clean rebuild"
  rm -rf -- "$VENV_DIR"
fi

export UV_CACHE_DIR
export UV_PYTHON_INSTALL_DIR="$PYTHON_INSTALL_DIR"
export UV_PYTHON_INSTALL_BIN=0
export UV_MANAGED_PYTHON=1
export UV_PYTHON="$PYTHON_VERSION"
unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME PYTHONPATH || true

cd "$ROOT_DIR"

log "Python $PYTHON_VERSION managed install"
"$UV_BIN" python install "$PYTHON_VERSION" --managed-python --no-bin

log "sync from uv.lock with --frozen"
"$UV_BIN" sync --frozen --managed-python

[[ -x "$VENV_DIR/bin/python" ]] || fail ".venv/bin/python was not created"
actual_python="$("$VENV_DIR/bin/python" -c 'import platform; print(platform.python_version())')"
[[ "$actual_python" == "$PYTHON_VERSION" ]] || \
  fail "environment Python is $actual_python; expected $PYTHON_VERSION"

log "environment smoke"
"$VENV_DIR/bin/python" -m unittest testCodes.test_python_environment -v
log "smoke PASS"
