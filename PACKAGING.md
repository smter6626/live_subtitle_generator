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

The manifest is contract-only in Step 2. Existing build scripts and PyInstaller specs do not consume it yet.

## Python environment

The future reproducible environment is `uv` + `pyproject.toml` + `uv.lock` + a project-local `.venv`, with Python `>=3.11`. The exact Python minor/patch and exact PySide6, PyInstaller, numpy, and sounddevice versions remain pending Step 3. A virtual environment is rebuilt from the version contract and lock; it is never preserved, migrated, or repaired as a release environment.

## whisper.cpp sources and pin

The Runtime source is pinned to:

```text
repository: https://github.com/ggml-org/whisper.cpp.git
commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
architecture: arm64
```

`external/whisper.cpp` is an ignored, local, reproducible checkout and build directory. It is not part of a fresh clone and must be recreated by the future bootstrap at the pinned commit.

`vendor/whisper.cpp` is tracked and contains the pinned upstream model download resource and its provenance. It does not contain whisper.cpp source, Runtime binaries, or models. The vendored script remains `vendor/whisper.cpp/download-ggml-model.sh` and is bundled as `Contents/Resources/bin/download-ggml-model.sh`.

The first frozen build profile is the successful old-machine profile: CMake 4.2.3, Unix Makefiles, Release, arm64, shared libraries, CPU, Metal, embedded Metal library, Accelerate/Apple BLAS, and `GGML_NATIVE=ON`. The full curated option set is in the Runtime manifest. `GGML_NATIVE=ON` is intentionally retained for this first profile but may affect portability across Apple Silicon generations; M4 Max and M5 acceptance must verify it.

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

Step 2 defines contracts only. It does not create a Python environment, bootstrap whisper.cpp, add the Finder build entry, change current build behavior, harden model downloads, build the App, or perform clean-machine acceptance.

The remaining implementation sequence is:

```text
Step 3  Rebuildable locked Python environment
Step 4  Pinned whisper.cpp Runtime bootstrap
Step 5  Double-click build entry and orchestration
Step 6  Strict packaging gates and post-build Runtime smoke
Step 7  Model download integrity, recovery, and retry
Step 8  Fresh Clone -> App -> real transcription acceptance
```

## Clean-machine validation

Clean-machine acceptance starts from a fresh `main` clone and the formal build entry. No copied `external/`, old virtual environment, manually compiled CLI, copied dynamic library or model, temporary `PATH` edit, or one-off repair command counts as a pass. Step 8 must exercise model download, microphone permission, real recording/transcription, Stop and microphone release, and verify `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
