# Packaging and Deployment Contract

## Goal and delivery flows

Classroom Live Transcriber targets macOS on Apple Silicon (`arm64`). A complete deployment must perform real local transcription; opening the UI or running `whisper-cli --help` alone is not acceptance.

The developer source-build flow starts at `git clone`. Run `Build ClassroomTranscriber.command` as the Finder-facing entry, or execute `scripts/bootstrap_and_build.sh` directly in a shell. The thin wrapper delegates all testable logic to the orchestrator, which prepares the locked Python environment and whisper.cpp Runtime, explicitly injects `.venv/bin/python` into the existing Release build, and produces `dist/ClassroomTranscriber.app`.

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

The Python and whisper.cpp source-build contracts are implemented by their bootstrap scripts and tests. The whisper Runtime bootstrap consumes the Manifest Build Profile directly. The Release and Debug specs, Runtime source preflight, packaged-copy normalization, and post-build verifier consume the same Manifest component and bundle records, so the required Runtime list is not duplicated across packaging stages.

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

## Model download integrity

`packaging/model_manifest.json` is the separate machine-readable contract for the five downloadable model artifacts. It freezes exact byte sizes and SHA-256 values from the official `ggerganov/whisper.cpp` Hugging Face repository blob/LFS metadata at revision `5359861c739e955e79d9a303bcbc70fb988958b1`; these values do not come from an old-machine model file. The Manifest records the official metadata endpoint, immutable artifact URLs, and upstream blob IDs. Model binaries remain outside Git, the App, and Runtime components.

Model Manager runs the unchanged vendored upstream downloader only inside a hidden temporary directory on the selected target filesystem. `model_integrity.py` rejects downloader failures, missing output, exact-size mismatch, or SHA-256 mismatch. Only a verified staging file is published with `os.replace`; a contract- and file-stat-bound hidden receipt is then written atomically. Normal scanning marks a file with an official downloadable filename available only while that receipt matches. An existing file without a receipt is fully verified in the existing background download worker before reuse, and an invalid existing file remains unavailable while retry removes stale managed staging and downloads a replacement. Explicit custom imports retain their existing local validation contract.

The model Manifest is bundled as `Contents/Resources/model_manifest.json`. Release/Debug specs, packaging source preflight, and the packaged Runtime verifier all require and validate it. Validate the repository copy independently with `.venv/bin/python model_integrity.py --manifest packaging/model_manifest.json`.

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

Logical component names are separate from the old build's observed ABI filenames in the manifest. The final packaged-copy gate validates their actual dependency closure with `otool`.

The existing bundle layout remains:

```text
ClassroomTranscriber.app/Contents/Resources/bin/
  whisper-cli
  required whisper/ggml dynamic libraries
  download-ggml-model.sh
```

## Fail-fast build contract

A formal Release build must fail when the Python environment or a critical package is missing, a required Runtime component is absent, a binary has the wrong architecture, RPath/dependency closure is incomplete, the vendored downloader is absent, or the post-build Runtime smoke fails. It must not emit a nominally complete but non-transcribing App after a warning.

`scripts/package_runtime.py` performs a strict Manifest-driven source preflight and normalizes only the Runtime copies inside the completed App: dylib install names and declared dependencies use `@rpath/<ABI filename>`, and every required component has the sole Runtime RPath `@loader_path`. The build then applies required ad-hoc signing and invokes `scripts/verify_packaged_runtime.py`. The verifier checks components, permissions, arm64-only Mach-O identity, semantic dependency closure, allowed system-library boundaries, downloader syntax, signature validity, bundled CLI smoke, and a second smoke from an isolated temporary Runtime directory. Any failure is nonzero and occurs before the build reports completion.

## One-entry developer build

The formal source-build chain is:

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
-> scripts/bootstrap_python_env.sh
-> scripts/bootstrap_whisper_runtime.sh
-> PYTHON=.venv/bin/python scripts/build_macos.sh
-> Manifest source preflight / packaged-copy normalization / ad-hoc signing
-> scripts/verify_packaged_runtime.py
-> dist/ClassroomTranscriber.app
```

The `.command` file only resolves the repository and transfers control. The orchestrator propagates failures and performs a basic App/bundle structure check. The Release build itself owns the strict packaged Runtime gate, so the formal one-entry flow cannot report success before verification passes. Ad-hoc signing is only the current development-bundle integrity step; Developer ID and notarization remain pending release work.

## Formal Release ZIP

After the formal build passes, create the ordinary-user artifact with an explicit version:

```bash
./Build\ ClassroomTranscriber.command
.venv/bin/python scripts/build_release_zip.py --version <version>
```

The source worktree must be clean so the recorded 40-character source commit identifies the packaged source. The artifact is `dist/ClassroomTranscriber-<version>-macOS-AppleSilicon.zip`. The Release entry reads the filename and payload contract from `packaging/runtime_manifest.json`; it never infers a version, changes the project version, creates a Git tag or GitHub Release, or uploads an asset.

Before publishing the ZIP, the entry re-runs the existing packaged Runtime verifier on `dist/ClassroomTranscriber.app`. It archives only `ClassroomTranscriber.app` with macOS `/usr/bin/zip -r -y -X`: `-y` preserves symlinks and `-X` excludes volatile extra fields such as access times, so repeated packaging of the same App produces identical archive bytes. It extracts with macOS `ditto` into a new temporary directory outside the source tree, checks archive boundaries and CRC, compares the complete bundle structure, file bytes, permission modes, and symlink targets, and then runs the same packaged Runtime verifier against the extracted App. A verification failure does not publish the staged ZIP. A successful run prints the version, source commit, artifact filename/path, exact byte size, SHA-256, and extracted-App verification result.

Models, `.venv`, `.tools`, `external`, source-tree files, build caches, and user settings are not Release payloads. Models remain an external Model Manager responsibility.

## Work still pending

The locked Python environment, whisper Runtime bootstrap, one-entry developer build orchestration, strict packaged Runtime gate, and transactional model download integrity layer are present. Their audit state is tracked separately. The project has not yet performed clean-machine acceptance and real transcription E2E.

The remaining implementation sequence is:

```text
Step 3  Rebuildable locked Python environment (implemented; audit status is tracked separately)
Step 4  Pinned whisper.cpp Runtime bootstrap (implementation supplied; audit status is tracked separately)
Step 5  Double-click build entry and orchestration (implemented; audit status is tracked separately)
Step 6  Strict packaging gates and post-build Runtime smoke (implemented; audit status is tracked separately)
Step 7  Model download integrity, recovery, and retry (implemented; audit status is tracked separately)
Step 8  Fresh Clone -> App -> real transcription acceptance
```

## Clean-machine validation

Clean-machine acceptance starts from a fresh `main` clone and the formal build entry. No copied `external/`, old virtual environment, manually compiled CLI, copied dynamic library or model, temporary `PATH` edit, or one-off repair command counts as a pass. Step 8 must exercise model download, microphone permission, real recording/transcription, Stop and microphone release, and verify `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
