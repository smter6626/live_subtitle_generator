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

ClassroomTranscriber.app/Contents/Resources/
  ClassroomTranscriber.icns
```

## App icon pipeline

The approved source artwork is tracked at `packaging/icons/ClassroomTranscriber.png`; the formal build never reads the original developer Downloads path. Its exact SHA-256 and repository-relative source/generated/bundle paths are frozen in `packaging/runtime_manifest.json`.

After cleaning generated output, `scripts/build_macos.sh` invokes `.venv/bin/python scripts/build_app_icon.py`. The generator validates the tracked source hash, square canvas, and minimum resolution, removes only the light matte connected to the canvas edge, creates a 1024 px RGBA master and the complete macOS iconset, then uses `/usr/bin/iconutil` to write `build/app-icon/ClassroomTranscriber.icns`. The generated iconset and ICNS stay under ignored temporary/build locations; they are rebuilt from the tracked PNG and script rather than committed as derived binaries.

The Release spec passes that ICNS to PyInstaller. The packaged Runtime verifier requires both `Contents/Resources/ClassroomTranscriber.icns` and the matching `CFBundleIconFile` entry in `Contents/Info.plist`, including ICNS header/length validation. Because the Release ZIP entry runs the same verifier before and after extraction and compares every bundle byte, icon preservation is part of the existing ZIP round-trip gate.

## Fail-fast build contract

A formal Release build must fail when the Python environment or a critical package is missing, the tracked App icon source/generation is invalid, a required Runtime component is absent, a binary has the wrong architecture, RPath/dependency closure is incomplete, the vendored downloader is absent, or the post-build Runtime smoke fails. It must not emit a nominally complete but non-transcribing App after a warning.

`scripts/package_runtime.py` performs a strict Manifest-driven source preflight and normalizes only the Runtime copies inside the completed App: dylib install names and declared dependencies use `@rpath/<ABI filename>`, and every required component has the sole Runtime RPath `@loader_path`. The build then applies required ad-hoc signing and invokes `scripts/verify_packaged_runtime.py`. The verifier checks components, permissions, arm64-only Mach-O identity, semantic dependency closure, allowed system-library boundaries, downloader syntax, signature validity, bundled CLI smoke, and a second smoke from an isolated temporary Runtime directory. Any failure is nonzero and occurs before the build reports completion.

## One-entry developer build

The formal source-build chain is:

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
-> scripts/bootstrap_python_env.sh
-> scripts/bootstrap_whisper_runtime.sh
-> PYTHON=.venv/bin/python scripts/build_macos.sh
-> Manifest-driven App icon generation
-> Manifest source preflight / packaged-copy normalization / ad-hoc signing
-> scripts/verify_packaged_runtime.py
-> scripts/release_identity.py -> dist/ClassroomTranscriber.app.provenance.json
-> dist/ClassroomTranscriber.app
```

The `.command` file only resolves the repository and transfers control. The orchestrator propagates failures and performs a basic App/bundle structure check. The Release build accepts only this clone's `.venv/bin/python` at Python 3.12.14 and a clean canonical source checkout. It cannot report success before Runtime verification and non-clobbering provenance generation pass. The provenance binds the source commit, exact release-contract bytes, complete App tree, and the code-defined REL1A build/verification tool set. The candidate uses ad-hoc signing and is not notarized.

## Formal Release ZIP

The fixed product identity is `1.1.0`, tag `1.1.0`, title `Classroom Transcriber 1.1.0`, App `ClassroomTranscriber.app`, and asset `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip`. This is an unbuilt, unpublished candidate; REL1A does not tag, upload, publish, or approve it. After a future real formal build passes, create one task-managed root under the current user's Downloads directory. The artifact and retained Human-review extraction must both be descendants of that root:

```bash
./Build\ ClassroomTranscriber.command
mkdir -p "$HOME/Downloads/classroom-transcriber-release/artifacts"
.venv/bin/python scripts/build_release_zip.py \
  --version 1.1.0 \
  --expected-source-commit "$(git rev-parse HEAD)" \
  --task-root "$HOME/Downloads/classroom-transcriber-release" \
  --artifact "$HOME/Downloads/classroom-transcriber-release/artifacts/ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip" \
  --human-review-extraction "$HOME/Downloads/classroom-transcriber-release/human-review"
```

The source worktree must be clean and HEAD must equal `--expected-source-commit`. The CLI always consumes this clone's tracked `packaging/runtime_manifest.json`, canonical `dist/ClassroomTranscriber.app`, and adjacent `dist/ClassroomTranscriber.app.provenance.json`; it does not accept alternate paths for those inputs. The project, lock, Release spec, bilingual notes, Runtime Manifest, App plist, and build provenance must all match the fixed release contract and provenance. The explicit task root must already exist beneath the current user's Downloads directory. Both caller-selected targets must be absent descendants of that root, and their parent directories must already exist. The entry never changes versions, creates a Git tag or GitHub Release, or uploads an asset.

Before exposing the ZIP, the entry re-runs the existing packaged Runtime verifier on `dist/ClassroomTranscriber.app`. It archives only `ClassroomTranscriber.app` with macOS `/usr/bin/zip -r -y -X`: `-y` preserves symlinks and `-X` excludes volatile extra fields such as access times, so repeated packaging of the same App produces identical archive bytes. It extracts with macOS `ditto` into the explicit retained Human-review directory, checks archive boundaries and CRC, compares the complete bundle structure, file bytes, permission modes, and symlink targets, and then runs the same packaged Runtime verifier against the extracted App. A verification failure removes the extraction and does not expose a final ZIP. Successful publication uses an atomic hard link that fails if a target appears, then prints the version, source commit, exact artifact path/byte size/SHA-256, and surviving Human-review extraction locator.

Models, `.venv`, `.tools`, `external`, source-tree files, build caches, and user settings are not Release payloads. Models remain an external Model Manager responsibility.

## Future 1.1.0 artifact work

The locked Python environment, whisper Runtime bootstrap, one-entry developer build orchestration, strict packaged Runtime gate, and transactional model download integrity layer are present. Historical clean-machine acceptance and real-transcription E2E were completed for Release 1.0.0, but that history does not accept an unbuilt 1.1.0 candidate or any future 1.1.0 App/ZIP bytes. REL1A's identity/provenance/ZIP foundation is locally accepted; REL1B's controller is a candidate awaiting independent review. A real 1.1.0 integration, fresh build, Human artifact review, and publication remain pending; REL1C is not implemented.

## REL1B approval, integration, and recovery

The candidate controller accepts exactly one positional command:

```text
release_controller.py status
release_controller.py integrate
release_controller.py resume
```

There are no repo, ref, path, signer, approval, fixture, or trust-root CLI options.
`integrate` and `resume` enter the same revalidation/reconciliation pipeline.
`status` validates approval, local source, journal and available local facts/logs;
it never creates directories, fetches, bootstraps, repairs, or pushes. Its
`*_RECORDED_UNVERIFIED` output is a recovery hint, not approval or proof of PASS.
Terminal failures are fixed codes; raw command output stays in local evidence.
The controller rejects build/package/human-pass/tag/draft/upload/publish.
REL1C must supply fresh artifact binding, genuine Human artifact PASS and
publication gates before any of those operations can become available.

Production is disabled without independent trust configuration. The proposed
fixed root is `/Library/Application Support/ClassroomTranscriberRelease/1.1.0`.
The root and `entry/scripts/` controller modules must be root-owned and unwritable
by the executing identity; directory/file modes are 0755/0644. Deployment and
production signing keys/approval creation require a separate Human decision and
were not performed in this implementation. Running the candidate repository
entry cannot authorize itself, even if a caller installs matching journal hashes.
The eventual protected entry must match `config.json` and the independently
approved implementation byte for byte.

`release_approval.py` uses OpenSSH detached signatures with a fixed signer and
production namespace. The protected root holds `config.json`, `allowed_signers`,
`approval.json`, `approval.json.sig`, `review.json`, `human.json`, and
`revoked.json`. Config binds an epoch, entry module hashes and review/owner
evidence hashes. Approval binds that config, signer bytes, full implementation
SHA, the code-defined complete tool set, parent/REL1B contract hashes, evidence
locators, exact repository/origin/main/feature/baseline/prior-feature values,
implementation/managed absolute paths and uid. Review and owner evidence must
refer to final Step 1 review/integration authorization; a REL1B local test PASS
cannot supply those future facts. Every stage rechecks signature, revocation,
source/tool bytes, configuration, paths and actual refs.

The production repository is `smter6626/live_subtitle_generator`; main is
`refs/heads/main` and feature is `refs/heads/codex/release-1-1-0-automation`.
The origin must be one of the fixed canonical SSH/HTTPS URLs and must be identical
for fetch and push. A small Git-config allowlist rejects extra remotes, hooks,
includes, URL rewrites, filters, custom SSH commands, alternates, replacement
objects and unsafe attributes. Transport uses no global/system Git config,
credential helper, SSH agent, SSH identity file or interactive prompt; HTTPS
redirects are disabled. Authenticated production transport is consequently not
established by these local tests. Do not loosen that isolation to work around a
transport failure; a future deployment decision must resolve the limitation.

Within one Downloads managed root, `journal.json` is 0600 and the root,
`evidence/`, `tmp/` and integration `clone/` are 0700. Writes use a same-directory
exclusive temporary file, file fsync, atomic replace and directory fsync. Unknown
or duplicate fields, symlinks, hard links, wrong modes and incomplete writes stop
execution. Checksums/log hashes/push receipts grant no authority. The actual
two-parent merge, tree, ancestry, tool bytes and live refs are independently
checked; content conflicts and drift stop rather than discard history.

Before the first environment executable or import, the gate requires absent
`.tools` and `.venv` and no ignored worktree inputs. It runs the accepted original
`bootstrap_python_env.sh`: pinned SHA-verified uv archive 0.12.5, newly installed
managed Python 3.12.14, clone-local cache and `uv sync --frozen`, then the original
environment smoke. A successful bootstrap establishes an **invocation-local
memory proof**, never a journal environment hash. The proof covers bytes,
identities/modes, link targets, Python stdlib, site packages including .pth/pyc
and native libraries, uv, venv config and all worktree inputs. Cache is excluded
after bootstrap and no sync/install follows. Probes run only after proof checks.
The gate checks it before/after full strict tests and before main push; replaced
environment or source makes it invalid. The strict command is:

```bash
.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s testCodes -v
```

Execution sets Qt offscreen, disables bytecode writes, removes inherited
Python/uv/Git/dyld overrides and uses the managed Downloads temporary directory.
Only the current invocation's gate can precede ordinary non-force main push.

Recovery is deliberately conservative. Before environment creation, verified
feature push and merge facts can be reconciled from exact Git objects/refs.
An existing environment on resume yields `ENVIRONMENT_UNTRUSTED` before execution;
this controller does not delete/rebuild it or reuse a persisted PASS. Preserve
the stopped managed root and request bounded independent reconciliation and a
new approved isolated attempt when necessary. Do not edit journal state to
force progress. Bootstrap/strict failures and environment changes leave main
unchanged. An exact feature ref prevents duplicate feature push even if its
receipt was lost or transport reported failure after the update. If main already
contains the expected merge, missing trusted local completion requires
`MAIN_PRESENT_HUMAN_RECONCILIATION`; no automatic COMPLETE, rollback or repeat
main push occurs. A missing/partial journal stops instead of being synthesized.

Tests use a Python-only `Policy` seam restricted to new `case-*` directories in
0700 `Downloads/rel1b-fixtures.*` roots and the exact local `remote.git`; fixtures
cannot use a production namespace or network origin. Fixture keys are new and
independent, and cannot be passed through production argparse. Fast state-machine
tests use a labelled callback gate or synthetic fault injection, which does not
prove pinned bootstrap/full-suite success. Independent real-gate smoke launchers
stay outside test discovery to avoid recursive integration tests; they must copy
the entire current source/testCodes, set `fixture_gate=None`, and retain bootstrap,
strict, operation-count and merge/ref evidence. No fixture is a real main merge.
The unchanged REL1A suite asserts canonical repository identity. Fixture gate
subprocesses therefore receive a canonical origin **reader view** via command
environment config, with network Git transports denied and the push URL fixed
to the local bare remote. The controller separately sanitizes its Git environment
and audits the actual local URLs/refs throughout. This test-only view does not
change `.git/config`, skip tests, substitute a gate, or enable production access.
Its isolated 0600 `git-reader.config` is created inside the new fixture root and
checked against code-defined bytes before use; it never reads user Git config.
uv configuration discovery is disabled so user uv settings cannot become gate
inputs; dependency metadata and frozen lock remain the approved project files.

For focused/full candidate checks, use this clone's already prepared Python,
set `QT_QPA_PLATFORM=offscreen` and `TMPDIR` to a newly recorded 0700 Downloads
fixture root, and run sequentially:

```bash
.venv/bin/python -B -W error::ResourceWarning -m unittest testCodes.test_release_approval testCodes.test_release_journal testCodes.test_release_controller -v
.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s testCodes -v
```

Keep logs and hashes for independent review. Offscreen/source/fixture checks do
not accept a packaged App, microphone behavior, Human gate or publication.

## Clean-machine validation

The completed Release 1.0.0 clean-machine acceptance remains historical evidence only. Future acceptance of exact 1.1.0 artifact bytes must start from a fresh canonical clone and the formal build entry. No copied `external/`, old virtual environment, manually compiled CLI, copied dynamic library or model, temporary `PATH` edit, or one-off repair command counts as a pass. That future 1.1.0 gate must exercise model download, microphone permission, real recording/transcription, Stop and microphone release, and verify `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
