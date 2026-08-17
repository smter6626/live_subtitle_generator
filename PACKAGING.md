# Packaging and Deployment Contract

## Goal and delivery flows

Classroom Live Transcriber targets macOS on Apple Silicon (`arm64`). A complete deployment must perform real local transcription; opening the UI or running `whisper-cli --help` alone is not acceptance.

The developer source-build flow starts at `git clone`. The formal project flow will prepare the Python environment, locked packages, whisper.cpp Runtime, and packaging dependencies, then produce `ClassroomTranscriber.app`. The future Finder entry is `Build ClassroomTranscriber.command`, a thin wrapper around `scripts/bootstrap_and_build.sh`.

The ordinary-user flow is:

```text
ClassroomTranscriber-<version>-macOS-AppleSilicon.zip
-> ClassroomTranscriber.app
-> Model Manager downloads a model
-> microphone permission
-> Start
-> real transcription
```

An ordinary user must not install or configure Git, Python, pip, uv, a virtual environment, CMake, whisper.cpp, `whisper-cli`, dynamic libraries, or `PATH` through Terminal. Models are not bundled in the App.

## Runtime manifest

`packaging/runtime_manifest.json` is the machine-readable deployment contract. It separates:

- `frozen`: decisions that later bootstrap and packaging work must implement;
- `observed`: evidence read from the successful old-machine build without preserving machine-specific paths;
- `pending`: values that a later Step must determine from evidence.

The Python and whisper.cpp source-build contracts are implemented by their bootstrap scripts and tests. The whisper Runtime bootstrap consumes the Manifest Build Profile directly; existing App build scripts and PyInstaller specs do not consume it yet.

## Python environment

The reproducible environment is `uv` 0.12.5 + `pyproject.toml` + `uv.lock` + `.python-version` + a project-local `.venv`. Python is frozen at 3.12.14 (`>=3.12,<3.13`) for this project environment. Direct dependencies are frozen at PySide6 6.11.1, numpy 2.5.2, sounddevice 0.5.6, and build/development dependency PyInstaller 6.22.1. The legacy optional `faster-whisper` fallback is not part of the current UI dependency contract.

Run `scripts/bootstrap_python_env.sh` from any working directory to ensure the environment, or pass `--recreate` to remove and rebuild only the project `.venv`. The script downloads the pinned macOS arm64 uv archive from the official Astral GitHub release, verifies its frozen SHA-256, and stores uv under `.tools/uv/`. uv installs its managed Python under `.tools/python/`, uses `.tools/cache/`, and performs `uv sync --frozen`; none of these generated directories are committed. It does not use the historical `venv/`, Homebrew, Conda, or the system Python to create the formal environment.

Normal bootstrap never changes `uv.lock`. A dependency update is explicit maintenance: edit `pyproject.toml`, use the pinned uv to regenerate the lock, run the environment and project tests, and commit both files. A virtual environment is rebuilt from the version contract and lock; it is never preserved, migrated, or repaired as a release environment.

## whisper.cpp sources and pin

The Runtime source is pinned to:

```text
repository: https://github.com/ggml-org/whisper.cpp.git
commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
architecture: arm64
```

`external/whisper.cpp` is an ignored, local, reproducible checkout and build directory. It is not part of a fresh clone and is recreated by `scripts/bootstrap_whisper_runtime.sh` at the pinned detached commit. The script rejects a non-official origin or a modified third-party worktree rather than overwriting it.

`vendor/whisper.cpp` is tracked and contains the pinned upstream model download resource and its provenance. It does not contain whisper.cpp source, Runtime binaries, or models. The vendored script remains `vendor/whisper.cpp/download-ggml-model.sh` and is bundled as `Contents/Resources/bin/download-ggml-model.sh`.

The first frozen build profile is the successful old-machine profile normalized for reproducibility: project-local CMake 4.2.3, Unix Makefiles, Release, explicit arm64, shared libraries, CPU, Metal, embedded Metal library, Accelerate/Apple BLAS, `GGML_OPENMP=OFF`, and `GGML_NATIVE=ON`. CMake is downloaded from Kitware's official universal macOS release artifact and verified with its frozen SHA-256. The complete option set is read from the Runtime manifest for a `cmake --fresh` configuration; the bootstrap only builds the `whisper-cli` target and dependencies.

Run `scripts/bootstrap_whisper_runtime.sh` after the Python bootstrap to ensure source, CMake, and Runtime. `--verify-only` performs no download, checkout, configure, or compile; it validates the pinned detached source, effective cache profile, required artifacts, arm64 architecture, source-build dependency/RPath boundaries, and the Manifest smoke command `whisper-cli --help`. `GGML_NATIVE=ON` is intentionally retained but may affect portability across Apple Silicon generations; M4 Max and M5 acceptance must verify it.

## Runtime components and bundle layout

The required logical Runtime components are:

```text
whisper-cli
libwhisper
libggml
libggml-base
libggml-cpu
libggml-blas
libggml-metal
```

Logical component names are separate from the old build's observed ABI filenames in the manifest. Later builds must validate the actual dependency closure with `otool`.

Step 2 preserves the current layout:

```text
ClassroomTranscriber.app/Contents/Resources/bin/
  whisper-cli
  required whisper/ggml dynamic libraries
  download-ggml-model.sh
```

## Fail-fast build contract

A formal Release build must fail when the Python environment or a critical package is missing, a required Runtime component is absent, a binary has the wrong architecture, RPath/dependency closure is incomplete, the vendored downloader is absent, or the post-build Runtime smoke fails. It must not emit a nominally complete but non-transcribing App after a warning.

## Work still pending

The locked Python environment and whisper Runtime bootstrap implementations are present. Their audit state is tracked separately. The project has not yet added the Finder build entry, changed current App build behavior, hardened model downloads, built the final App, or performed clean-machine acceptance.

The remaining implementation sequence is:

```text
Step 3  Rebuildable locked Python environment (implemented; audit status is tracked separately)
Step 4  Pinned whisper.cpp Runtime bootstrap (implementation supplied; audit status is tracked separately)
Step 5  Double-click build entry and orchestration
Step 6  Strict packaging gates and post-build Runtime smoke
Step 7  Model download integrity, recovery, and retry
Step 8  Fresh Clone -> App -> real transcription acceptance
```

## Clean-machine validation

Clean-machine acceptance starts from a fresh `main` clone and the formal build entry. No copied `external/`, old virtual environment, manually compiled CLI, copied dynamic library or model, temporary `PATH` edit, or one-off repair command counts as a pass. Step 8 must exercise model download, microphone permission, real recording/transcription, Stop and microphone release, and verify `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
