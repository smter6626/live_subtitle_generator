# Packaging and Deployment Contract

## Current published artifact -- 1.1.0

The formal release is [Classroom Transcriber 1.1.0](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.1.0). Its single ZIP is 48,307,378 bytes with SHA-256 `fbe14de7d68c519ddb817ef1f45166f3e39a24f0a27d290cd82d9c2c20717bdb`, built from source `014a609fcc7ab26be8820f4399cdaa19225498e1`. See [release details](docs/release_1_1_0.md) for package, Human-review and publication verification scope. Documentation-only commits after publication do not move that tag or rebuild the ZIP.

The legacy implementation/candidate and signed-entry sections below preserve protocol history, not current release status. Current execution uses the Owner-authorized lightweight workflow. Release 1.1.0 does not require a user to modify Homebrew permissions or use Terminal: any maintainer-side transport preparation is outside the App and ZIP.

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

The fixed product identity is `1.1.0`, tag `1.1.0`, title `Classroom Transcriber 1.1.0`, App `ClassroomTranscriber.app`, and asset `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip`. The published package is fixed above; the following commands document the packaging interface, not instructions to replace that package. REL1A itself does not tag, upload, publish, or approve a ZIP. A new build requires a new artifact and Human decision. The artifact and retained Human-review extraction must both be descendants of one task-managed Downloads root:

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

## Artifact acceptance and historical coverage

The locked Python environment, whisper Runtime bootstrap, one-entry developer build orchestration, strict packaged Runtime gate, and transactional model download integrity layer are present. Release 1.1.0 completed actual integration, a 297-test strict source gate, fresh formal build, automatic and independent package checks, Owner testing and same-ZIP publication. This accepts only the exact artifact recorded above, not every hardware/language/model combination or a future rebuilt ZIP. Historical 1.0.0 clean-machine testing remains separate evidence.

## Current lightweight release workflow

The Owner selected the explicit lightweight entry instead of deploying the old
protected-entry/signature scheme. This is prompt-based Reviewer/Executor control:
the Reviewer records real decisions, the agent prepares the exact final package,
the Human tests it and explicitly permits publication, then the agent publishes
those same bytes. It does not promise cryptographic approval independence from a
malicious same-uid writer. The legacy sections below remain compatibility history,
not a requirement to install root-owned tools, signing keys, groups or auth bridges.

```bash
.venv/bin/python -B scripts/release_lightweight.py \
  --approval /absolute/Downloads/task/decisions/approval.json status
```

The same prefix accepts `integrate`, `prepare`, `resume`, `human-gate`, and `publish`.
For the completed 1.1.0 publication, native Homebrew's group-writable `Cellar`
needed an explicit, temporary maintainer-side permission transaction; the original
mode was restored on every exit. GitHub returned `untagged-*` links for the draft
release and its asset. The strict original Publisher rejected them; a reviewed,
task-local adapter accepted only the observed exact release/asset IDs and draft
links, while retaining the original state machine and all source, receipt, notes,
tag, asset and actual-download checks. Published URLs still had to use `1.1.0`.
The shipped App/source/ZIP were not changed. Before a future release, address these
transport compatibility issues explicitly rather than copying old IDs, disabling
checks or assuming the original entry will work unmodified in every environment.
Only `status` is a local read-only hint. `integrate` runs the original isolated
two-parent Integration and live full strict gate, including ordinary feature/main
push, then stops for independent final-main review. `prepare` runs that stage if
no source decision exists; with a valid source decision it calls the original
BuildController and stops at exact-artifact Human review. Six inherited-pipe
checkpoints, fresh pinned environments, Runtime verification, canonical provenance,
ZIP CRC/boundary/bytes/modes/symlink correspondence and retained extraction are
unchanged. No existing artifact is rebuilt by `prepare`. `resume` starts no missing
work, never restores an environment proof from a hash, and uses the original
conservative unknown-build and publication reconciliation routes.

### Ordinary local records

Use a dedicated 0700 `decisions/` outside the source and workflow output roots.
JSON records are canonical JSON (sorted keys, compact separators, ASCII escapes,
one final newline), 0600 regular single-link files, with no symlink ancestors.
These are audit records, not secrets or signing keys. The Reviewer creates them
only when the referenced decision actually exists; they are never tracked in Git.

`approval.json` has exactly the fields defined in
`release_lightweight_approval.APPROVAL_FIELDS`. A schematic example follows;
angle-bracket values must be replaced by independently checked actual facts:

```json
{
  "schema_version": 1,
  "mode": "lightweight",
  "id": "release-1-1-0-reviewed-attempt",
  "accepted_commit": "<full implementation SHA>",
  "tools": {"<every LIGHTWEIGHT_REQUIRED_TOOLS path>": "<actual SHA-256>"},
  "contracts": {"parent": "<current Static SHA-256>", "rel1c": "<current C Static SHA-256>"},
  "reviewer_reference": "conversation-implementation-review-ACCEPT",
  "integration_authorization_reference": "conversation-owner-integration-authorized",
  "repository": "smter6626/live_subtitle_generator",
  "origin": "git@github.com:smter6626/live_subtitle_generator.git",
  "main_ref": "refs/heads/main",
  "feature_ref": "refs/heads/codex/release-1-1-0-automation",
  "main": "<fresh remote main SHA>",
  "feature_prior": null,
  "baseline": "<actual sole merge-base SHA>",
  "implementation": "/absolute/Downloads/implementation",
  "managed": "/absolute/Downloads/task/integration",
  "workflow": "/absolute/Downloads/task/workflow",
  "uid": 501
}
```

The UID is the actual executing UID, not necessarily 501. `feature_prior` is null
only if a fresh remote check proves the fixed feature ref absent. The tools map
must cover the code-defined complete `LIGHTWEIGHT_REQUIRED_TOOLS` set, including
both new entry/approval helpers, with actual reviewed bytes, not arbitrary caller
subsets. Parent/REL1C Static hashes and all source/ref/path identities are rechecked.
No config epoch, signer list, revocation registry or `.sig` is used in this mode.
Existing state key `trust_sha256` holds only the contract-input hash for schema
compatibility; it is not an independently protected trust root.

Each subsequent record uses the same five common fields:

```json
{
  "schema_version": 1,
  "id": "unique-local-decision-id",
  "purpose": "<fixed purpose for this file>",
  "authorization_sha256": "<SHA-256 of exact approval.json bytes>",
  "decision_reference": "conversation-real-independent-decision-reference"
}
```

IDs/references are 1..80 ASCII letters, digits, `_` or `-`; keep a readable link
from this compact reference to the actual conversation/evidence in the task audit.
Do not replace a missing Human response with an invented reference.

| File and fixed purpose | Additional exact fields / preparation |
| --- | --- |
| `integration.json`: `independent-final-main-source` | `decision: "ACCEPT"`, `source_repository`, `source_commit`, `source_tree`, ordered `parents`, `baseline`, `main_ref`, `feature_ref`, `final_main`, `final_feature`, `evidence_sha256`. The Reviewer derives these from actual Git/strict results and puts compact independent evidence in adjacent `integration-evidence.json`; its bytes are hashed. Source must be the managed `clone`, with actual parents `[original main, accepted implementation]`, both ancestors, verified tree/tools and current refs. |
| `artifact-human.json`: `owner-exact-artifact-decision` | `decision: "PASS"` or `"FAIL"`, `publish_allowed: true` only after explicit Human permission, `integration_receipt_sha256`, `artifact`. Copy the entire exact validated artifact object from workflow state, including source, ZIP path/size/hash, retained App tree/path and build/package log hashes. PASS without explicit allow is insufficient. A failed test must never set PASS. |
| `publication-plan.json`: `owner-fixed-publication-plan` | `artifact_id`, `human_receipt_sha256`, `source_commit`, `source_tree`, fixed `notes_sha256`, explicit integer `tag_timestamp`, deterministic `tag_oid`, `transport`. Native transport is exactly `{"executable": "<resolved existing gh path>", "sha256": "<actual executable hash>"}`. It is not a credential directory or token. The annotated tag object is computed from the exact source/timestamp using `release_publication.tag_identity`. |
| `publication-reconciliation.json`: `owner-exact-publication-reconciliation` | Needed only for cross-invocation remote objects/unknown results. `plan_sha256`, `artifact_id`, `human_receipt_sha256`, `source_commit`, `tag_oid`, observed positive integer `release_id`, positive integer/null `asset_id`, `phase: "DRAFT"`, `"UPLOADED"` or `"PUBLISHED"`. The main Reviewer explicitly verifies observed IDs, full metadata, ownership history and package bindings before recording the real reference. Matching names/fields or rehashing advanced state alone never grant adoption. |

For example, after the Human tests the exact retained App and explicitly permits
release, the ordinary artifact record combines those five common fields with:

```json
{
  "decision": "PASS",
  "publish_allowed": true,
  "integration_receipt_sha256": "<exact integration.json SHA-256>",
  "artifact": "<complete current validated artifact object, not a Boolean>"
}
```

These are schema illustrations, not ready-made PASS records. The agent must not
pre-create Human PASS, use synthetic fixture records in production, or fabricate
a decision. Missing/wrong-purpose/changed records, FAIL, no explicit allow, changed
source, ZIP or retained App stop before tag/draft/upload. Every publication write
revalidates actual source and package bytes. Rebuilds use new attempts and need
new Human testing; historical 1.0.0 or source/offscreen PASS is not artifact PASS.

### Native authentication and recovery

Only the explicit `LightweightPolicy` entry selects scoped native transport;
legacy/nested mixed-policy routing is rejected and the context resets in `finally`.
Git uses its normal existing login/config/SSH agent, gh uses its normal login and
resolved executable hash. The controller never reads private keys or token/config
contents, extracts tokens, copies credentials, runs auth login/setup-git, or changes
global config. Caller Git/Python/dyld/UV/token overrides are not inherited. Fixed
repo/origin/refs and repository-local config/hooks/object audits still apply.

The original Publisher supplies fixed tag/title/notes/one asset, UTF-8 JSON stdin,
binary upload, exact draft download before publication, formal/latest verification
and a new public download with the same size/SHA. No force, overwrite, clobber,
foreign same-name adoption or automatic history deletion is added. Unknown effects
first reconcile actual remote facts, then stop for a genuine Reviewer reference
where ownership cannot be established; no blind duplicate create/upload occurs.
No log or notification contains credentials or a complete environment dump.

Tests use a distinct Python-only `LightweightPolicy` seam limited to new 0700
`Downloads/rel1c-lightweight-fixtures.*/case-*` roots, exact local `remote.git`,
case-local fake gh and an isolated HOME. Production CLI cannot select this seam,
test root, fake origin or callback/synthetic build. Fixture Runtime/App/strict
gates are labelled synthetic and do not count as real delivery or Human PASS.

## REL1B approval, integration, and recovery

This section and the legacy C1/C2 sections below describe the retained protected
entries. Their deployment/signature/auth-bridge requirements are superseded for
the current lightweight entry above, not outstanding Owner approval requests.

The accepted REL1B controller accepts exactly one positional command:

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

## REL1C1 candidate receipts and recovery

C1 was independently accepted for its bounded local implementation scope. The
expanded CLI is `status|build|resume|human-gate|prepare|pipeline-status|pipeline-resume|publish`;
it has no options. Publication is separately gated below. Production remains disabled without separately deployed
root-owned trust/entry and final Step 1 approval. No production trust, personal
credentials, formal App/ZIP or real external release objects were created here.

Authorization uses the existing trust root, fixed Owner signer and OpenSSH route.
`workflow-config.json` independently binds an epoch and the complete control/helper
protected entry, including release_identity, build_release_zip, verify_packaged_runtime,
model_integrity and resource_paths. Protected model/runtime/product-contract data and
accepted-source bytes are also bound. The CLI strips caller import paths and verifies
the protected locations, independent signature and exact bytes before loading helpers;
it compiles verified source rather than trusting cached bytecode. `workflow-approval.json`/`.sig` has the code-defined
`release-workflow-control` purpose and exact legacy-plus-C1 tool set. It binds the
accepted implementation, current parent/REL1B/REL1C static contract hashes and the
existing final-Step-1 review and Owner-integration records. A payload cannot select
a smaller set. Legacy `config.json`/`approval.json` and the four-module REL1B entry
keep their original validation. Revocation/config/tool replacements stop both
receipt validation and dependent work; fixture policies are Python-only seams
restricted to new `Downloads/rel1c1-fixtures.*/case-*` trees, local bare remotes and
a distinct fixture signer/namespace. They cannot be selected by production CLI.

The independently signed `integration.json`/`.sig` uses purpose
`independent-final-main-source` and the fixed signing namespace suffix
`-integration`. It requires an explicit ACCEPT decision and binds the full final main commit/tree, exact ordered merge
parents, baseline, accepted implementation/tools/contracts, applicable final refs,
managed integration clone, external integration-evidence hash and decision reference.
The validator audits Git before repository commands, checks actual commit/tree
objects, ancestry, all tracked bytes (including hidden index drift), required tools
and source HEAD. Build additionally checks real remote refs. Journal COMPLETE,
process success and old PASS logs do not authorize source acceptance.

Build persists BUILD intent before creating a new unique attempt and clean clone of
that exact signed final source. It accepts no ignored interpreter, tools, old dist or
copied environment. The original `bootstrap_and_build.sh` retains its normal developer/
Finder behavior, argv/order and child failures. Controlled invocation uses fixed
before/after Python, Runtime and App events over inherited request/ack pipes and a
separate parent-lifetime pipe. There is no hook command/executable or CLI override.
Denial, missing/invalid/duplicate/out-of-order events, child failure and parent loss
stop the active session before further stages. The controller closes pipes and waits
for child termination, escalating to kill when necessary.

Every checkpoint rechecks independent approval, exact source/tools/contracts/pins,
remote refs and the identity/bytes of all previously acquired inputs. Python may
create `.tools/{uv,python,cache}` and `.venv`; Runtime may create the pinned
`.tools/cmake/4.2.3` and `external/whisper.cpp` source/build; App may create `build`
and `dist`, including generated icon and PyInstaller cache. Existing files cannot
change at these boundaries. Cache/interpreter/site-package/third-party bytes remain
in the snapshot rather than being blanket exclusions. The uv cache advisory lock
`.tools/cache/.lock`, like the Python/virtualenv advisory locks,
has a narrow writable-file exception: current-owner, empty regular single-link file
with mode `0666`, reached through real current-owner directories with no group/other
write permission in the fresh controlled workspace. Other writable cache files,
nonempty locks, lock/root aliases and unsafe ancestry are refused. The cache lock remains in
the proof with device/inode, owner/mode, size, modification/change timestamps and
SHA-256 of its bytes; later replacement or modification stops before the next stage.
An offline regression uses the identity-checked local pinned uv binary to initialize
a new empty cache with `uv cache prune --offline`; this is cache maintenance only,
with no interpreter acquisition or formal build. A second offline regression uses
the identity-checked pinned uv and current clone interpreter to install a locally
generated minimal synthetic wheel with `UV_LINK_MODE=copy`, no index, and Python
downloads disabled into a fresh outside-source Downloads fixture. It requires a
populated native wheel-cache directory link and checks the real target bytes.

C1 also handles one expected side effect of the first validation after fresh
Python acquisition. It retains the legacy exact Python prefix/base executable,
version, pinned uv version and `uv lock --check --offline` checks. The full input
proof, including source/tool bytes and identity, is checked before each command.
External authority/Git/source facts receive the full audit at verification entry
and exit and at the surrounding checkpoints. Only that first
successful, fixed lock-check command can add at most one interpreter record at
`.tools/cache/interpreter-v4/<16-lowercase-hex-key>/<16-lowercase-hex>.msgpack`.
The record must be a current-owner, single-link regular file, 1..65536 bytes,
mode 0600 or 0644; at most its root/key ancestors may be new real directories,
mode 0700 or 0755. Every prior cache/source/tool/interpreter item must remain
identical. Python probing and uv version checks cannot create any inputs. The
complete post-command scan and external-authority revalidation must both pass
before this one-time acquisition commits to the proof; the checkpoint then rechecks
the frozen tree before acknowledgement. Failure consumes the permission without adopting changed bytes;
later checks have no creation permission, including for another valid-shaped
interpreter record. Unknown uv layouts, larger/multiple records, aliases,
unsafe owners/modes and prior-item replacement stop for review, not automatic
compatibility expansion. No cache directory or external validation cache is
excluded or trusted from persisted state. Synchronous verification has a 20s
budget and the original shell's 30s acknowledgement/lifetime protocol is unchanged.
Each verifier has a newly owned process group. Timeout, exception or surviving
background descendants stops validation and kills/reaps that group only; cleanup
uncertainty cannot grant a successful environment proof.
The native regression uses the original SHA-verified Python bootstrap on complete
fresh tracked sources, not an old interpreter: actual uv/Python acquisition,
frozen sync, original environment smoke, lock check and all six checkpoints run.
Runtime/App children remain signed synthetic fixtures, never a formal build.

Cache directory links are supported only at `wheels-v6/pypi/<package>/<wheel>` or
`wheels-v6/url/<source>/<package>/<wheel>`, pointing by relative text directly to a
real `archive-v0/<id>` directory inside the same freshly acquired `.tools/cache`.
The workspace, `.tools`, cache root, link ancestry and target ancestry remain real,
current-owner and safely permissioned. Target resolution cannot pass through other
aliases. Escaping, broken/cyclic, absolute or unrelated directory aliases, foreign
owners, writable targets/contents and malformed locks fail closed. Cache file links
also require real safe targets inside the same cache. The snapshot records link
device/inode/owner/mode, text, link count, size and modification/change timestamps;
it traverses every real cache directory and hashes every regular file, including
the archive targets. No directory link is traversed as an alternate tree or used to
exclude target bytes. Later link replacement/retargeting, real directory replacement,
target byte changes or interpreter drift stops before Runtime. Signed synthetic
children reproduce both native wheel link layouts and the advisory lock in the
six-checkpoint controller/package test. These regressions prove the specified local
cache boundary, not production readiness, whole Step 1 acceptance or Human artifact
PASS. The pinned Runtime source
and tracked bytes are validated, and its original verifier runs with the acquired
interpreter. App provenance is checked after a successful fresh invocation, then
the original ZIP helper returns actual `ReleaseMetadata`. Snapshot proof exists only
in that invocation's memory; version output and stored checksums cannot replace it.
Most tests use independently signed, explicitly synthetic stage scripts and a separate
fixture Runtime verifier seam. The native Python regression above establishes only
its fresh pinned Python acquisition/validation route, not a formal Runtime/App build
or whole-release success. The fixture seams are unavailable from production CLI.

The artifact layer consumes the existing ZIP helper's `ReleaseMetadata`, canonical
App-adjacent provenance and original round-trip checks. Fixtures exercise the real
ZIP/CRC/bytes/modes/symlink implementation with explicitly synthetic Runtime
verification. `fix_metadata` fixes package facts; it cannot prove fresh build or grant
Owner acceptance. The controller requires its live invocation-local proof before recording an artifact. Identity includes exact ZIP absolute
path/size/hash, source/tree/receipt, tools/contracts, App name/bundle identifier/both
versions/tree, build/package evidence hashes and the surviving Human directory.
Subsequent gates recheck actual files, safe ancestry and single-link regular files.
They also compare the archive directly with the accepted bundle snapshot definition:
all members, file bytes/sizes, modes, types, directory structure and symlink targets
must match the retained App. Duplicate/aliased/missing/extra members fail even when
metadata/state/provenance are recomputed and a purpose-correct fixture receipt is signed.
This comparison writes no scratch files, including during read-only status.

`artifact-human.json`/`.sig` is a separately signed Owner decision, purpose
`owner-exact-artifact-decision`, fixed namespace suffix `-artifact-human`. Its strict
schema includes receipt ID, PASS/FAIL, external Owner decision reference, trust/config
and authorization identities, repository/version, accepted tools/contracts, source
receipt hash and the complete exact artifact identity. `validate_human_gate` is a
callable future C2 gate and reauthenticates/rechecks on every consultation. A signed
FAIL stops. A forged/revoked/wrong-purpose receipt, integration approval, Boolean
flag, lost receipt, recomputed metadata/state/provenance or replacement ZIP/App cannot
grant PASS. No workflow command signs decisions. Human PASS alone does not enable
publication; a separately signed plan and approved transport are required.

Workflow storage is a signed separate Downloads path, never beneath REL1B's managed
journal or implementation source. The layout is `state.json`, `attempts/<id>/source`,
`artifacts/<id>/<fixed ZIP name>`, `human/<id>/ClassroomTranscriber.app`,
`evidence/<id>/{build,package}.log`, and `tmp`. Controlled directories are 0700;
state/logs are 0600. Intent writes use exclusive same-directory temporary files,
file fsync, atomic replacement and directory fsync. Partial/unknown storage stops
without repair. New attempts use unique IDs and preserve prior paths. A checksummed
state is a recovery hint, never authorization or an environment proof.

`status` is strictly local/read-only: no receipt acceptance, fetch, bootstrap, packaged
executable, directory creation or state write. It prints `*_RECORDED_UNVERIFIED`.
`resume` checks surviving artifact facts as unverified records. For BUILDING, BUILT
or PACKAGING it revalidates source/approval and persists REVIEW_REQUIRED without
executing or accepting surviving outputs. An explicit later `build` uses a fresh
unique attempt; old workspace, logs, artifacts and Human extraction are never reused
or overwritten. Partial persistence stops for review. An ARTIFACT label or checksum
cannot reconstruct a lost invocation-local build proof. `human-gate` validates before persisting
HUMAN_CHECK intent and revalidates before/after recording a receipt. Receipt loss or
file replacement stops subsequent Human checks. Recorded Human state does not enable
publication; receipt/signature validation remains mandatory for every future action.

Future Human procedure: obtain the exact ZIP's verified retained-App locator from
the independently accepted build outcome. Open that App in Finder, with the normal
Privacy & Security → Open Anyway route if needed. Test external model acquisition,
microphone permission, Start/Stop and a second Session, Original Language/.en
compatibility, display reset/incremental copy, bounded window/scrolling, bilingual
Clean toolbar/path controls, active/stopped no-clobber rename and R2 full-history
Yes/No recovery. Record hardware/language/model coverage and decide PASS/FAIL through
the separate trusted signing path. Keep the exact ZIP and extraction untouched.
A rebuild or changed bytes requires fresh automated verification and Owner review.
Historical 1.0.0 M4 Max/M5 testing does not approve this unbuilt 1.1.0 candidate or
claim coverage of every offered language. PT-REL-01 closure belongs to independent
governance review; the notes/hash correction here does not close it.

## C2/C3 publication pipeline and production gates

This implementation candidate is awaiting independent review. No production
trust, credentials, source integration, formal build, artifact PASS, tag or release
has been created by the implementation/tests. Fixture success is not production
readiness. The current formal download remains 1.0.0.

Release notes now use phase-neutral version changes/install/limits language, with
fixed SHA-256 `69013bcae2de876202b3c6d2633fcb75a659b1f5f413cd905295eb6431a12703`
bound in the contract, identity helper, Publisher and direct tests. They neither
claim that a package exists nor claim it remains unbuilt after publication. The
contract's unchanged `candidate-unbuilt-unpublished` status is a static preparation
identity label, NOT a live release outcome; signed artifact/Human receipts and
actual GitHub facts determine delivery state. Historical C1 notes/hash acceptance
remains historical; new note bytes require final implementation review/regression.

The protected workflow entry exposes `prepare`, `pipeline-status`, `pipeline-resume` and `publish`
alongside C1 commands. Its pre-import bootstrap and signed complete tool set now
include `release_publication.py`, `release_publication_state.py` and
`release_pipeline.py`. Verified source bytes are compiled, not caller imports/pyc.
Legacy REL1B retains its original default scope/namespace and authentication isolation.
An exact code-type switch lets WorkflowPolicy reuse the original Integration
with the complete Workflow tool closure; no payload chooses a weaker scope.

`prepare` invokes Integration, stops at `FINAL_MAIN_REVIEW_REQUIRED`, then uses a
valid independently signed exact-main receipt on a later invocation to call the
original BuildController. It ends at `EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED`.
Existing artifacts are revalidated, never rebuilt/overwritten by preparation.
Interrupted build/package recovery remains C1's conservative retirement plus an
explicit fresh attempt. No command signs review, integration or Human decisions.
`pipeline-status` is local/read-only, never contacts GitHub, creates files, repairs,
accepts a receipt or executes a stage. All recorded states stay UNVERIFIED.

`pipeline-resume` does not start absent work. Existing publication enters Publisher
and rechecks all exact decisions/remote ownership; a build/package interruption
only calls the original C1 retirement path, never rebuilds automatically. An existing
artifact receives C1's local unverified validation. An unfinished integration uses
the original Integration recovery; COMPLETE stops before a next stage. The original
`resume` contract remains unchanged.

| Local hint | What to inspect / explicit later command |
| --- | --- |
| MISSING | Check final Step 1/Owner/transport deployment, then explicitly `prepare` |
| INTEGRATION_* | Check original journal/facts; `pipeline-resume` cannot supply independent final-main ACCEPT |
| BUILDING/BUILT/PACKAGING | `pipeline-resume` retires unknown outcome; review, then explicit fresh `prepare` |
| ARTIFACT/HUMAN_RECORDED | Inspect exact retained ZIP/App and current external decision; `human-gate`/`publish` only when gates actually validate |
| PUBLICATION_* | Inspect stopped facts and obtain exact external reconciliation; `pipeline-resume` revalidates, never trusts the hint |

This table does not validate a receipt or grant permission from a stage label.

### Publication decisions and recovery

The external signing path supplies `publication-plan.json`/`.sig`, purpose
`owner-fixed-publication-plan`. The existing common receipt fields bind epoch,
signer/trust/config/authorization, current tools/contracts/repository/version,
accepted commit and an external decision reference. Additional fields bind
`artifact_id`, exact Human receipt hash, source commit/tree, fixed notes hash,
tag timestamp/object ID and transport. The annotated tag bytes are deterministic
and independently fixed by the plan; both remote object ID and peeled commit are
required. No implicit/default-branch tag creation is used.

Publishing persists intent before each side effect, revalidates current signed
source/Human/artifact/plan before and after writes and at recovery/complete, and
checks remote draft metadata/tag/unique asset after the publish-intent boundary.
It compares actual downloaded draft bytes before PATCH, requests `make_latest`
as the REST string `"true"`, then verifies public/latest objects, tag and newly
downloaded bytes. The unique fixed ZIP must retain its exact size/hash. POST must
return HTTP 201; GET/PATCH require 200. JSON bodies use UTF-8 stdin, explicit
methods and fixed host/endpoint; no `--repo`, field-magic, clobber or deletion.
Lists are paginated completely and duplicate IDs/schema/HTTP errors stop.
Binary upload uses the fixed file directly. Download spools HTTP bytes to a new
0600 file with a 120s owned-process-group bound, parses at most 64KiB headers,
then uses 1MiB chunks and exact size/SHA checks to create a new exclusive ZIP.
Raw responses and partial files remain local; no ZIP is decoded or printed.

Publication hints live at `workflow/publication/{state.json,downloads/}` with
0700 directories/0600 state/files, strict stage-intent-ID schemas, checksum,
file fsync/atomic replace/directory fsync. A valid checksum, saved ID or matching
remote fields never proves ownership. Within one invocation only a successful
HTTP 201 plus exact read-back establishes newly created object IDs. Across
invocations, even a previously recorded COMPLETE, release/asset recovery requires
external `publication-reconciliation.json`/`.sig`, purpose
`owner-exact-publication-reconciliation`, binding plan/artifact/Human/source/tag,
exact release/asset IDs and phase `DRAFT`, `UPLOADED` or `PUBLISHED`. Every remote
field and actual download is checked again; advanced state cannot skip this gate.
Unknown create/upload/publish results first read remote objects and then stop for
that independent reconciliation, with no blind replay. No matching object also
remains uncertain and requires review. A 502-created `starter` asset is retained
for Human disposition, never automatically deleted. An externally reconciled
already-public object is verified by a new public download without claiming that
this invocation performed or proved the historical draft download.

### Still-required production Owner decisions

These are blocking production gates, not nonblocking pending work:

1. Independently controlled trust/signing/receipt path, protected full entry and
   trustworthy fixed bootstrap Python. The proposed root remains
   `/Library/Application Support/ClassroomTranscriberRelease/1.1.0`; no deployment
   or production private key creation/read is performed here. Ordinary Agents
   cannot write accepted reviews, source decisions or exact-artifact PASS.
2. Specific least-privilege Git and GitHub authenticated transport. Git still
   disables credential helpers/global config/SSH identity and agent, so production
   push authentication is NOT established. Owner must explicitly decide a bounded
   transport before real integration, followed by a bounded Git protocol extension
   and independent review. Deploying the gh group alone cannot authenticate Git
   pushes or make `prepare` production-ready. Do not loosen isolation or use Codex Mix OAuth.

The gh proposal uses a signed exact resolved executable/hash and fixed
`<trust-root>/github-auth`. Owner chooses an explicitly dedicated group ID; there
is no automatic staff/default group. Directory is root-owned 0750; only
`config.yml`/`hosts.yml`, root-owned 0440 with that group, regular/single-link/no
symlink, are allowed. The executing uid must be in the approved group and have
read/traverse but no write access. Python checks metadata only; gh reads the
approved credentials. No token is extracted, inherited, passed in environment or
written to evidence. No group/key/auth directory is created during implementation.
Credential refresh cannot write back; it requires independent Owner maintenance
and updated approval as applicable, not silent fallback to a personal gh home.
Fixture Policy instead uses only its newly created case-local fake executable and
0700 gh-config; no production CLI flag selects it or addresses the network.

After implementation acceptance and both deployment/transport gates, the approved
controller can integrate/fix source and build the final ZIP. Only that exact ZIP's
Human PASS permits tag/draft/upload/publish. Human uses the retained extraction's
App and verifies microphone/model/Start/Stop/second Session/Clean/window/language/
rename/recovery; offscreen/synthetic/old-App results cannot supply this PASS.

### Parent implementation coverage (candidate, not acceptance)

| Parent criterion | Implementation route | Remaining real-delivery evidence |
| --- | --- | --- |
| REL-AC-01 | Protected complete closure, fixed pipeline, separate signed purposes | Independent Step 1 acceptance and production deployment |
| REL-AC-02 | Accepted REL1A identity/pins/notes and fixed publication constants | Actual final App/source/tag values |
| REL-AC-03 | Original audited divergent two-parent Integration/live gate | Real authenticated feature/main push and independent final-source receipt |
| REL-AC-04 | Original C1 six-checkpoint build/provenance/ZIP chain | Fresh formal Runtime/App/ZIP, not synthetic fixtures |
| REL-AC-05 | Current signed exact-artifact Human validator at every write boundary | Human black-box PASS on those exact final bytes |
| REL-AC-06 | Actual fake-gh argv/binary/tag/draft/download/latest tests | Real GitHub object IDs/public download bytes |
| REL-AC-07 | Original local recovery plus signed remote-ID reconciliation | Real interruption/ref/API reconciliation when applicable |
| REL-AC-08 | Bilingual docs, privacy, local readonly hints and tracked-source tests | Independent governance closure and accurate post-publication links |

Single writer is still assumed. Read checks and writes are not an atomic remote
transaction; observed boundary changes stop. No lock/concurrency/automatic rollback
guarantee, and no cleaner deletes active audit or recovery evidence.

## Clean-machine validation

The completed Release 1.0.0 clean-machine acceptance remains historical evidence only. Future acceptance of exact 1.1.0 artifact bytes must start from a fresh canonical clone and the formal build entry. No copied `external/`, old virtual environment, manually compiled CLI, copied dynamic library or model, temporary `PATH` edit, or one-off repair command counts as a pass. That future 1.1.0 gate must exercise model download, microphone permission, real recording/transcription, Stop and microphone release, and verify `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
