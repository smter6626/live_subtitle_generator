# Classroom Live Transcriber — Repository Map

## Document identity and authority

| Field | Value |
| --- | --- |
| Repository | `smter6626/live_subtitle_generator` (Classroom Live Transcriber) |
| Branch | Historical `main`/`codex/clean-toolbar-rename-v1` baseline plus `codex/release-1-1-0-automation`; real feature/main integration remains pending |
| Structural baseline | Original full scan at `4d2059d273d0ba94373b1969b8236ef462b6acae`; affected architecture ownership/flows updated through Product Polish Step 1F, session clipboard UI commit `cb4261825b7d51d3ec33a97e083683c50e6b9e82`, window-layout commit `569e5c551c101811ed80fca23bd5708d6ac880cf`, and final Clean full-text recovery R2 commit `fb317ea4a2b1db557133e91590e852c0241a3cd8`. |
| Updated | 2026-10-07; explicit lightweight entry/local decisions/native authentication over retained release controllers |
| Scan scope | 65 Git-tracked files at the original map baseline; later structural syncs update affected ownership/flows without re-running a full-file recount |
| Document role | A derived architecture and change-navigation aid, not a product contract or API reference |

Authority hierarchy:

1. **Implementation truth**: the current tracked source, scripts, manifests, and tests define the behavior this map describes.
2. **Long-term contract**: `docs/*_static.md` defines durable direction and hard boundaries.
3. **Execution state and confirmed evidence**: `docs/*_runtime.md` records the current/previous work-state and acceptance evidence.
4. **This Repo Map**: a compact, derived guide to ownership, dependencies, side effects, and likely change impact.

If this map conflicts with current source, update the map; do not change source merely to conform to this document. Likewise, a future Product Polish decision belongs in the relevant static/runtime documents and implementation review, not in this map.

The scan intentionally excludes `.git/`, `.venv/`, `.tools/`, `build/`, `dist/`, bytecode caches, local `models/`, local `outputs/`, and the full ignored `external/whisper.cpp` third-party tree. The map does record first-party code that creates, consumes, packages, or verifies those locations.

## Repository overview

```text
PySide6 UI (ui_app.py)
  -> TranscriptionController
      -> TranscriptionEngine
          -> sounddevice capture + queue + WhisperCppBackend
          -> TranscriptStore evidence session

UI Model Manager -> model_manager -> model_integrity -> vendored downloader / model filesystem
                             \-> App settings JSON

resource_paths + settings select source-mode or frozen-App resources and writable locations

Build wrapper -> Python bootstrap -> whisper.cpp bootstrap -> App-icon generator -> PyInstaller -> Runtime normalizer
             -> packaged Runtime verifier -> App -> Release ZIP round-trip verifier
```

| Area | Primary ownership |
| --- | --- |
| Desktop UI and Qt event boundary | `ui_app.py`, `crash_debug.py` |
| Session orchestration and state | `transcription_controller.py` |
| Live capture, chunk scheduling, inference work, dedup, event production | `transcription_engine.py`, shared helpers in `stream_transcribe.py` |
| ASR backend command/parsing helpers and legacy CLI path | `stream_transcribe.py` |
| Session evidence persistence | `transcript_store.py` plus configuration serialization in `settings.py` |
| Paths, defaults, and runtime validation | `resource_paths.py`, `settings.py` |
| Model discovery, selection/import/download UI support, app settings | `model_manager.py`, `ui_app.py` |
| Downloadable-model integrity transaction | `model_integrity.py`, `packaging/model_manifest.json` |
| Reproducible source runtime and App packaging | `scripts/`, `packaging/runtime_manifest.json`, `packaging/icons/`, PyInstaller specs |
| Release identity, App provenance, artifact creation and validation | `packaging/release_contract.json`, `scripts/release_identity.py`, `scripts/build_release_zip.py` |
| Independent integration approval, recovery hints and live Git/test gate | `scripts/release_approval.py`, `scripts/release_journal.py`, `scripts/release_integration.py`, `scripts/release_controller.py` |
| C1 workflow, exact-source receipt, artifact facts and independent Human decision | `scripts/release_workflow.py`, `release_workflow_state.py`, `release_artifact.py`, `release_human_gate.py`; independent workflow scope in `release_approval.py` |
| Contract and regression coverage | `testCodes/` |
| Governance, current state, user/build documentation | `README.md`, `README.zh-CN.md`, `PACKAGING.md`, `docs/` |

## File and module map

### REL1C control ownership

The current Human-authorized entry is `release_lightweight.py --approval <absolute
local record> status|integrate|prepare|resume|human-gate|publish`. It selects an exact,
independent `LightweightPolicy` and ordinary purpose-specific Reviewer/Human audit
records in `release_lightweight_approval.py`. This new implementation awaits its own
independent review; it does not establish a formal package or published release.

The entry reuses Integration, BuildController, artifact/state and Publisher/pipeline,
not a second Agent loop. Native Git/gh authentication is scoped to this explicit
policy; caller token/config/import overrides are not inherited, legacy or different
nested policies are rejected, and the context always resets. Source/build/ZIP and
fixed remote-object checks remain unchanged. `artifact-human` additionally requires
explicit `publish_allowed: true`; ordinary references record actual decisions,
without a signing key or same-uid cryptographic anti-forgery promise. Legacy root/
signature entries below remain compatible but are not current deployment gates.

| New module | Responsibility / boundary | Direct regression |
| --- | --- | --- |
| `scripts/release_lightweight.py` | Explicit local-approval CLI and scoped native transport; routes only to the original controllers. No CLI fixture/fake-origin switch or automatic Human PASS. | `test_release_lightweight.py`; exact CLI refusal, local Git/checkpoints/ZIP/fake-gh and read-only status. |
| `scripts/release_lightweight_approval.py` | Strict ordinary local approval/decision-reference/complete tool-contract input identities; validates purpose-specific source, Human allow, plan and exact-ID reconciliation records. No config epoch, signer, signature, key or production auth deployment. | `test_release_lightweight.py`; schema/path/reference/tool drift, missing or wrong Human decision/allow and changed artifact rejection. |

C1's synchronous inherited-pipe build/package controller was independently accepted.
C2/C3 adds fixed publication and routing candidates awaiting independent review.
Production deployment, authenticated Git transport and real integration/build/Human/
publication remain pending. Local implementation acceptance does not accept new App bytes.

| Module | Responsibility / boundary | Direct regression |
| --- | --- | --- |
| `release_workflow.py` | Fixed status/build/resume/human-gate/prepare/pipeline-status/pipeline-resume/publish CLI, complete protected pre-import closure, unchanged C1 fresh source/build/ZIP boundaries and routing to separately gated publication. | `test_release_workflow.py`, `test_release_pipeline.py`; actual CLI refusal and snapshots. |
| `release_workflow_state.py` | Strict separate C1 recovery hints, 0700/0600 atomic persistence, unique attempts, intent/outcome and conservative stop after partial/unknown storage. Does not enlarge the REL1B journal. | `test_release_workflow_state.py`; fsync/replace crashes, schema/path refusal. |
| `release_artifact.py` | Independently authenticated exact main source plus audited Git/byte facts; validated `ReleaseMetadata`, canonical provenance, exact ZIP/App/retained-directory identities and rechecks. Every consultation also compares actual ZIP members to retained App bytes/modes/types/links; package facts alone do not prove a fresh build. | `test_release_artifact.py`; real local Git/signatures/ZIP and synthetic App verifier. |
| `release_human_gate.py` | Callable separately signed exact-artifact Owner PASS/FAIL validator. Cannot sign decisions; every consultation reauthenticates and checks current files. | `test_release_human_gate.py`; valid signed fixture PASS and adversarial receipts/replacements. |
| `release_approval.py` C1 scope | Fixed complete loaded control/helper closure and relevant protected data, complete build/C1 tools and parent/REL1B/REL1C contracts; distinct workflow configuration and purpose-specific receipts through existing trust/signature route. Legacy entry/default checks remain intact. | `test_release_approval.py` legacy and C1 scope tests. |
| `release_publication.py` | Signed fixed plan/transport/Human/source validation, deterministic annotated tag, actual gh API UTF-8/binary requests, draft/public downloads and formal/latest checks. Cross-invocation remote IDs require independent signed reconciliation, not journal adoption. | `test_release_publication.py`; actual fake-gh subprocess and local bare tag, malformed/drift/crash cases. |
| `release_publication_state.py` | Separate 0700/0600 atomic publication hints with strict stage/intent/ID/download schemas; checksum never grants ownership or PASS. | `test_release_publication_state.py`; rehash/permissions/atomic/read-only tests. |
| `release_pipeline.py` | Reuses Integration, BuildController and Publisher; stops for independent final-main and exact-artifact decisions, never signs them or invents a second implementation loop. | `test_release_pipeline.py`; local two-parent/real original Python/six-checkpoint/ZIP/fake-gh chain with explicit synthetic limits. |

The separate workflow layout retains `attempts`, `artifacts`, `human`, `evidence`, `tmp`,
`state.json` and the optional fixed `publication` directory. None grants acceptance.
Publication is a gated candidate; production deployment/authentication remain absent.
Build proof is invocation-local and cannot
be recovered from checksummed state. See PACKAGING for exact CLI, checkpoint paths,
receipt fields, retained-App Human procedure and recovery boundaries.

### Runtime application modules

| Path | Responsibility and important interface | Dependencies / primary users | State, side effects, and likely change impact |
| --- | --- | --- | --- |
| `ui_app.py` | PySide6 entry point (`main`), `MainWindow`, `ModelManagerDialog`, `TranscriptTable`, translation lookup, and `EventBridge`. Owns visible controls, screen-aware main-window height bounds, the left controls scroll surface, transcript/log widgets, dialog lifecycle, Start/Stop requests, UI refresh, live UI-language switching, current-session display reset, and Clean rename/recovery/path/text actions. | Uses Qt screen available geometry plus `TranscriptionController`, model-manager functions, settings constants, transcript parsers, and crash logging. It is the PyInstaller entry. | Reveal/Copy Path share a left-controls row; Rename/Copy New Text sit in the Clean toolbar before Jump to Live. Raw/Logs have no rename or Clean-copy actions. Clean path actions request current writer identity verification from the Store; conclusive path absence can offer bilingual complete-history recovery, while uncertain inspection fails closed. Rename/recovery does not clear rows, counts, scroll, or copy cursor. |
| `transcription_controller.py` | Session state machine (`EngineState`) and public `start(...)` / `stop()` / `rename_clean(...)` / `recover_clean(...)`. Creates normalized runtime settings, validates them, creates the session store, assigns UUID plus monotonic generation ownership, then owns the engine instance. Converts owned engine events to controller/UI events. | Uses `default_settings` and `validate_runtime_paths`, `TranscriptStore`, `TranscriptionEngine`; constructed by `MainWindow`. | Rename and recovery check current session ID and generation, then delegate to the current store. Stop never holds the controller's session lock while joining workers, avoiding a lock-order deadlock. File-operation validation never changes engine state. |
| `transcription_engine.py` | Stable live-ASR implementation: capture loop, worker loop, 48 kHz capture / 16 kHz resample, 10 s chunks with 3 s overlap, final partial handling, clean-layer hallucination filter, queue events, and `stop()` drain/close behavior. | Uses `sounddevice`, `numpy`, `TranscriptionSettings`, `WhisperCppBackend` and dedup/resample helpers from `stream_transcribe.py`, and `TranscriptStore`. Created only by the controller. | Owns audio ring buffer, task queue, worker/capture threads, stop event, prior clean text. Opens the microphone; creates temporary WAVs indirectly through the backend; invokes subprocess inference; appends evidence and emits events. Changes have high ASR, microphone, evidence, timing, and UI-thread impact. |
| `stream_transcribe.py` | Shared ASR helpers: exact/fuzzy boundary dedup, resampling, PCM WAV writer, whisper.cpp command creation/output parsing, and `WhisperCppBackend`. It also retains a separate legacy console streaming runner and optional `FasterWhisperBackend`. | Imported by settings and the production engine; directly exercised by ASR tests. The standalone `main()` is not the normal UI path. | `WhisperCppBackend.transcribe_chunk()` creates a temporary WAV and runs `whisper-cli`; legacy `main()` opens a microphone and appends timestamped root-level raw/clean files. Editing shared helpers affects both UI runtime and legacy CLI/regression cases. |
| `transcript_store.py` | Creates one timestamp-named session directory; writes/flushes `raw.txt`, `clean.txt`, `session.log`, and `config.json`; validates stems; atomically renames Clean without replacement; captures exact Clean-writer bytes and can publish a verified no-clobber recovery when the writer has no Session `.txt` path; parses displayable transcript lines. | Uses `settings.write_config_json`; used by controller, engine, UI, and tests. | The Clean lock coordinates append, inspection/snapshot, rename, recovery/writer switch, and close. Close retains a trusted exact snapshot for post-Stop recovery. Directory and writer identities gate every path result; uncertain I/O fails closed. New Sessions still start at `clean.txt`. Unsupported no-replace platforms fail closed. |
| `settings.py` | Defines transcriber defaults, UI/original-language normalization and mapping, output-base-to-`outputs` resolution, `TranscriptionSettings`, preflight of CLI/model/output/beam/task, and config JSON serialization. | Reads path choices from `resource_paths.py` and chunk constants from `stream_transcribe.py`; used by controller, engine, model manager, UI, and tests. | Establishes source-vs-frozen defaults. `TranscriptionSettings.to_config()` becomes session `config.json`; `validate_runtime_paths()` validates executable/model/runtime values and output writability before session creation. Changes reach command arguments, saved evidence, UI labels, and test fixtures. |
| `resource_paths.py` | Detects frozen App mode and resolves project resources, bundled resources, writable config/output/model directories, model scan roots, and source/frozen CLI/downloader/manifest paths. | Used by settings, model integrity, crash diagnostics, and model-download resource tests. | Selects source-tree versus user Library/Documents/App bundle paths; no writes itself. A path change affects settings persistence, packaged resource discovery, source mode, and Model Manager scanning. |
| `model_manager.py` | Defines `ModelInfo` and persisted `AppSettings`; scans/deduplicates model files, computes availability, validates imports, selects defaults, builds the vendored downloader command, and delegates safe download/publish. | Loads the model contract from `model_integrity.py`; consumes settings/path defaults; called by UI and tests. | Reads/writes `config/settings.json` in source mode or Application Support in frozen mode, including output base and UI language; creates/checks model directories; launches the downloader subprocess through an injectable runner. `ModelInfo.current_summary_label` provides concise current summaries, while `display_label` retains path information for combo/log presentation; tooltips/table keep full paths accessible. |
| `model_integrity.py` | Validates the model manifest, hashes exact model bytes, handles receipts, removes stale managed staging, and runs the staging -> validate -> atomic publish transaction. CLI `main()` validates the manifest. | Uses model-manifest path from `resource_paths.py`; called by model manager and packaged verifier. | Reads model files; creates/removes hidden staging directories and receipt files; uses `os.replace` for final model and receipt. A failure keeps managed official filenames unavailable. This is the authority for integrity transaction semantics, not the dialog. |
| `crash_debug.py` | Best-effort crash/startup diagnostics and exception hooks. | Called by `ui_app.py`. | Appends a crash log under user Application Support; intentionally swallows logging failures. Does not control transcription behavior, but failure-handling changes can affect diagnosis. |
| `transcribe.py` | Minimal old `faster_whisper` one-file sample. | Independently imports optional `faster_whisper`; not referenced by the UI or formal environment. | Reads a fixed WAV if run. Treat as legacy/manual experiment, not a supported runtime interface. |

### Build, bootstrap, packaging, and release

| Path | Role / interface | Dependencies and side effects | Change impact / related tests |
| --- | --- | --- | --- |
| `Build ClassroomTranscriber.command` | Finder-facing, thin formal build entry. | Resolves the repo root and `exec`s `scripts/bootstrap_and_build.sh`. | Must remain portable and thin. `test_build_orchestration.py`. |
| `scripts/bootstrap_and_build.sh` | Formal one-entry build orchestrator. | Requires macOS arm64; calls the Python bootstrap, Runtime bootstrap, then injects `.venv/bin/python` into the Release build; checks the produced `.app`; the C1 inherited-pipe mode synchronously authorizes before/after each stage and stops on parent lifetime EOF. | The main developer-build boundary. `test_build_orchestration.py`, packaging/runtime tests. |
| `scripts/bootstrap_python_env.sh` | Creates or, with `--recreate`, removes/rebuilds the project `.venv` from pinned uv/Python/lock metadata. | Downloads and SHA-checks uv when needed; writes ignored `.tools/` and `.venv/`; runs environment contract tests. | Dependency lock, formal interpreter, and destructive recreate behavior are sensitive. `test_python_environment.py`, `test_runtime_manifest.py`. |
| `scripts/bootstrap_whisper_runtime.sh` | Rebuilds or verifies (`--verify-only`) the pinned ignored whisper.cpp Runtime. | Uses manifest values through `whisper_runtime_contract.py`; may download CMake and clone/build `external/whisper.cpp`; refuses dirty/unexpected third-party state. | Controls third-party Runtime provenance and generated binary closure. `test_whisper_runtime_bootstrap.py`, `test_runtime_manifest.py`. |
| `scripts/whisper_runtime_contract.py` | Manifest reader and source-Runtime verifier; commands: `get`, `cmake-arguments`, `artifact-records`, `verify-runtime`. | Reads `runtime_manifest.json`; invokes Git, `file`, `otool`, and the CLI smoke during verification. | Centralizes build-profile/data interpretation. Do not duplicate manifest facts in bootstrap code. Bootstrap/manifest tests protect it. |
| `scripts/build_app_icon.py` | Manifest-driven macOS icon generator. | Validates the tracked source SHA/canvas, removes its edge-connected light matte, renders a 1024 px RGBA master and complete iconset with locked PySide6/NumPy, then calls macOS `iconutil`; writes only ignored temporary/`build/` output. | Reproducible icon quality and generated ICNS boundary. `test_app_icon.py`, manifest/packaging tests. |
| `scripts/build_macos.sh` | Formal Release App build and hard gate. | Requires clean canonical source and this clone's Python 3.12.14 `.venv`, deletes generated `build/` and `dist/`, generates the icon, runs PyInstaller, normalizes, ad-hoc signs, verifies, then writes non-clobbering canonical App provenance. | Build success semantics and generated artifacts. `test_release_identity.py`, `test_app_icon.py`, `test_packaged_runtime.py`, `test_build_orchestration.py`. |
| `scripts/build_macos_debug.sh` | Separate console/debug PyInstaller build. | Deletes its generated debug outputs and applies permissive debug RPath adjustments. | Not the formal Release gate; changes should be checked against the Debug spec and manual debug use. |
| `scripts/package_runtime.py` | Manifest-driven source preflight and post-PyInstaller App Runtime normalizer; subcommands `validate-sources` and `normalize-app`. | Reads manifest and model contract; modifies copied App binaries with `install_name_tool`, permissions, and resource checks. | High-risk package closure boundary; `test_packaged_runtime.py`. |
| `scripts/verify_packaged_runtime.py` | Read-only packaged-App verifier. | Checks both App plist versions equal 1.1.0, the icon resource/ICNS/`CFBundleIconFile`, required Runtime files, arm64, RPaths/dependency closure, downloader/model manifest, codesign, bundled CLI smoke, and isolated Runtime smoke. | Formal build and Release ZIP trust boundary; `test_packaged_runtime.py` and `test_release_zip.py`. |
| `scripts/release_identity.py` | Fixed REL1A identity and canonical build-provenance helper. | Validates project/lock/App/notes/contract identity and repository origin; hashes the complete App tree, release contract, and a code-defined complete REL1A tool set; writes and validates exact canonical provenance. | Does not integrate, approve, tag, upload, publish, or control a release. `test_release_identity.py`. |
| `scripts/release_controller.py` | Closed `status` / `integrate` / `resume` argparse and fixed-code reporting. | Uses approval, journal and integration helpers; production has no input/trust/fixture overrides. | Status is local read-only; missing independent production trust disables execution. Build/package/Human-pass/tag/draft/upload/publish remain REL1C and unavailable. |
| `scripts/release_approval.py` | Fixed protected external trust root, code-defined tool set, detached OpenSSH signature, exact schema and no-follow path checks. | Binds implementation SHA, all tools, contracts, independent review/owner evidence, exact Git refs/origin and managed paths; validates config and revocation each stage. | Root-owned protected entry deployment and production keys/approval are pending Human decisions, not installed by this candidate. `test_release_approval.py`. |
| `scripts/release_journal.py` | Atomic 0600 journal in a 0700 Downloads managed root, closed stages/intents and evidence validation. | fsync file, atomic replace, fsync directory; approval-bound recovery hints only. | A checksum, PASS log or push receipt is not authority. Partial/unsafe persistence stops; no automatic repair. `test_release_journal.py`. |
| `scripts/release_integration.py` | Audited isolated clone, exact object acquisition, divergent two-parent merge, feature/main ordinary pushes and live environment/full strict gate. | Revalidates approval/source/Git config/refs at stage boundaries; uses original pinned bootstrap from absent environment and invocation-local byte/identity snapshots of uv, Python, environment code and worktree. | Existing environments stop before execution, including resume. Replacements invalidate the gate; exact feature ref avoids repeated pushes; already-updated main requires read-only Human reconciliation. Transport isolation does not establish production authentication. `test_release_controller.py`. |
| `scripts/build_release_zip.py` | Formal fixed-1.1.0 Release ZIP entry. | Requires formal Python, macOS arm64, clean HEAD equal to an explicit commit, this clone's canonical Runtime Manifest/App/provenance, and absent artifact/extraction paths beneath one explicit Downloads task root; stages, verifies, retains extraction, and publishes with atomic no-clobber semantics. | Release payload boundary only. `test_release_zip.py`. |
| `scripts/clean_build.sh` | Developer cleanup tool. | Deletes generated `build/`, `dist/`, and selected caches while preserving models, outputs, external Runtime, and historical `venv/`. | Destructive only for generated locations; not called by formal build. |
| `run_long_test.sh` | Legacy long-running console transcription and system-monitoring helper. | Starts the legacy stream runner, writes ignored test-run logs, samples macOS system tools, and contains a machine-specific developer path. | It is not portable and not part of the formal build/release path; its current maintenance status is not established by source. |

### Manifests, specs, dependency files, and vendor material

| Path / group | Responsibility | Used by / change impact |
| --- | --- | --- |
| `packaging/runtime_manifest.json` | Machine-readable frozen Runtime/build/bundle/release contract plus observed/pending metadata. Enumerates the seven required Runtime components, vendored downloader, model-manifest location, App-icon source/hash/generated/bundle paths, formal build entry, and release filename template. | Consumed by bootstrap/icon helpers, PyInstaller specs, Runtime normalizer/verifier, Release ZIP code, and manifest tests. It is the packaging data source of truth. |
| `packaging/release_contract.json`, `RELEASE_NOTES_1.1.0.md` | Compact fixed 1.1.0 product/repository/candidate identity and its exact bilingual candidate notes. | Consumed and byte-bound by `release_identity.py`; describes an unbuilt, unpublished, ad-hoc-signed, non-notarized candidate with external models. |
| `packaging/model_manifest.json` | Frozen five-model download metadata: filename, exact byte count, SHA-256, upstream revision/provenance, staging and receipt policy. | Loaded by `model_integrity.py`; indirectly drives Model Manager availability/download list; bundled and verified in the App. `test_model_integrity.py`, `test_model_download_resources.py`, packaging tests. |
| `packaging/icons/ClassroomTranscriber.png` | Tracked, user-approved square source artwork for the formal App icon; the Manifest freezes its SHA-256. | Read only by `build_app_icon.py`; the source is normalized/generated during formal build, never loaded from a developer Downloads path. `test_app_icon.py`, `test_runtime_manifest.py`. |
| `packaging/ClassroomTranscriber.spec` | Release PyInstaller spec; entry is `ui_app.py`, data list and generated icon path are manifest-derived, microphone usage string is declared, and `BUNDLE` receives the generated `ClassroomTranscriber.icns`. | Called by Release build; PyInstaller writes the ICNS resource and `CFBundleIconFile`. `test_packaged_runtime.py`. |
| `packaging/ClassroomTranscriberDebug.spec` | Console/debug counterpart of the Release spec with the same manifest-derived data resources. | Used by debug build; packaging tests assert both specs follow the manifest. |
| `pyproject.toml`, `uv.lock`, `.python-version` | Formal dependency/version declarations for uv and the project-local Python environment. | Used by Python bootstrap and environment/manifest tests. `uv.lock` is a generated-but-tracked lock, unlike runtime build products. |
| `.gitignore` | Defines ignored runtime, model, build, settings, and third-party build directories. | Explains why these locations are excluded from this map; changes can alter release/worktree hygiene assumptions. |
| `vendor/whisper.cpp/download-ggml-model.sh` | Tracked upstream downloader invoked only from Model Manager staging. | Used by `model_manager.py` and bundled into the App. It supplies download transport, while first-party integrity code decides whether bytes are available. |
| `vendor/whisper.cpp/UPSTREAM.md`, `vendor/whisper.cpp/LICENSE`, `THIRD_PARTY_NOTICES.md` | Provenance/license record for the vendored downloader. | Update together when rebasing the vendor resource; they are not Runtime source or model binaries. |

### Tests: coverage map

Tests are a mix of `unittest` contract suites and directly executable regression scripts. They primarily protect interfaces and behavior named below; they are not a complete GUI or real-microphone acceptance suite.

| Test set | Production boundary protected | Main coverage |
| --- | --- | --- |
| `test_backends.py` | `stream_transcribe.py` backends/helpers | whisper.cpp command building/parsing, WAV writing, backend availability/smoke pathways; optional faster-whisper checks when requested. |
| `test_dedup_cases.py`, `test_dedup_expanded_cases.py`, `test_dedup_uncovered_cases.py`, `test_pseudo_real_chunk_sequences.py`, `test_pseudo_real_boundary_sequences.py`, `test_pseudo_real_boundary_sequences_v3.py` | Stable `simple_dedup()` / `fuzzy_boundary_dedup()` behavior | Exact, fuzzy, and pseudo-real overlap sequences. Run before touching dedup thresholds, tokenization, or transcript boundary handling. |
| `test_ui_support.py` | `resource_paths.py`, `settings.py`, `model_manager.py`, `transcript_store.py`, `transcription_engine.py`, shared backend helpers | Path/model/settings serialization, language command mapping, evidence append, hallucination filtering, final-partial/queue/Stop worker behavior. It is the broad source-runtime safety regression suite. |
| `test_window_layout.py` | `ui_app.py` main-window layout and Qt event ownership | Injected available geometries, show/resize/screen handlers, minimum-height behavior, controls scrollbar/wheel/focus reachability, independent Clean/Raw/Logs scrolling, and bilingual retranslation. |
| `test_clean_rename.py` | `transcript_store.py`, `transcription_controller.py`, `ui_app.py` | Active/stopped rename and recovery, exact byte order, append serialization, current Session ownership, no-clobber collisions/races, unsafe and uncertain paths, failure cleanup/writer preservation, bilingual confirmation/No/retry, Finder/clipboard failure closure, toolbar location, and path/cursor/layout behavior. |
| `test_model_download_resources.py` | `resource_paths.py`, `model_manager.py`, vendor resource, model manifest | Source/frozen downloader and manifest selection, executable vendor script, supported models, and independence from ignored `external/`. |
| `test_model_integrity.py` | `model_integrity.py`, `model_manager.py`, model manifest | Manifest validity, staging/publish/receipt behavior, size/SHA failures, corrupt/existing files, retry, custom import distinction, and receipt invalidation. |
| `test_model_manager_ui_contract.py` | `ui_app.py` Model Manager orchestration and model presentation/selection/download-feedback contracts | Guards concise summaries/full-path access, explicit-selection confirmation source/timer semantics, automatic no-confirm paths, and indeterminate download busy state/cleanup while preserving worker/integrity boundaries. |
| `test_output_root.py`, `test_ui_language.py` | Persisted Product Polish settings and MainWindow/controller integration | Backward-compatible output-base/UI-language settings, `<base>/outputs` mapping and preflight, live bilingual retranslation, and independence from Original Language/ASR state. |
| `test_python_environment.py` | `pyproject.toml`, lock/version declarations, formal environment | Exact Python and package versions, managed project environment, and safe production imports. |
| `test_runtime_manifest.py` | `runtime_manifest.json` and related dependency declarations | Manifest schema/portability/no-secret rules, pinned Runtime/build profile, component list, model-integrity/App-icon packaging linkage, and declared environment alignment. |
| `test_app_icon.py` | Tracked source artwork, `build_app_icon.py`, and App-icon Manifest contract | Source SHA/path portability, 1024 px RGBA normalization with transparent corners, and real `iconutil` ICNS generation/structure. |
| `test_whisper_runtime_bootstrap.py` | Runtime bootstrap/helper and manifest | CMake acquisition, manifest-derived CMake profile, component/smoke completeness, and repo-relative bootstrap facts. |
| `test_build_orchestration.py` | `.command`, orchestrator, formal build metadata | Executable/syntax requirements, thin wrapper, formal stage order, formal Python injection, expected App checks, and portability. |
| `test_packaged_runtime.py` | specs, `build_macos.sh`, package normalizer, packaged verifier | Manifest-driven collection/icon wiring; order of icon generation/preflight/normalize/sign/verify; missing component/dependency/downloader/manifest/icon failures; architecture and smoke gates. |
| `test_release_identity.py` | Fixed project/release identity and App build provenance | Project/lock/spec/notes/asset agreement, unchanged schema/dependency pins, wrong identity/App versions/notes, non-clobber provenance, and stale App/source/contract/required-tool bindings. |
| `test_release_approval.py` | Independent fixture signature/protected production entry | Complete tool binding, signer/namespace, contract/config/evidence/revocation/schema/path tampering; no production fixture authority. |
| `test_release_journal.py` | Durable recovery hints | Permissions, no-follow/hard-link/schema/checksum rejection, rehashed authority changes, atomic write/fsync failures and incomplete persistence. |
| `test_release_controller.py` | Actual argparse/Integration/local Git pipeline | True divergent merge and docs/ancestry/tree, callback-gate state-machine/crash tests, counterfeit environment rejection without execution, synthetic environment replacement faults, content conflict, URL/hook/config/ref drift, read-only status, actual ref plus operation-count reconciliation. Callback/synthetic gates do not prove production bootstrap/full-suite success; an independent full-source real-gate launcher belongs outside discovery. |
| `test_release_zip.py` | `build_release_zip.py` and packaged verifier handoff | Fixed identity/locked Python/clean expected source/canonical manifest-App-provenance inputs, Downloads task-root and no-clobber targets, durable extraction, deterministic ZIP round-trip, exclusions, path/symlink safety, verifier failure handling, and exact digest. |

### Documentation and historical material

| Path / group | Current role in this repository map |
| --- | --- |
| `docs/` | Stable contracts, runtime/acceptance history, architecture/change-navigation, and governance documentation; specific document roles are listed below. |
| `docs/product_polish_static.md`, `docs/product_polish_runtime.md` | Current Product/UX stable contract and execution state. This Repo Map reflects source through the Step 1B implementation commit; ACTIVE-step state remains owned by runtime. |
| `docs/deployment_static.md`, `docs/deployment_runtime.md` | Deployment/release stable contract and recorded execution evidence; Deployment currently has no ACTIVE step. |
| `README.md` | Primary English user-facing GitHub landing page and usage guide. |
| `README.zh-CN.md` | Complete Simplified Chinese user-facing equivalent of `README.md`. |
| `PACKAGING.md` | Developer packaging, reproducible build, Runtime verification, and Release ZIP documentation. |
| `docs/工程细节.md` | Detailed explanatory engineering narrative; useful orientation, but secondary to current source/manifests/static/runtime. |
| `docs/LLM_POSTPROCESSING_DESIGN.md`, `docs/LLMsteps.md`, `docs/goalForNextLevel.md`, `docs/user_understand.md` | Design/backlog material for an LLM sidecar and later directions. It does not describe a tracked LLM implementation on current `main`; its input path is gated on a not-yet-implemented trusted current-Clean resolver. |
| `docs/Yeming_Dai_Audio_Transcription_Portfolio.md` | Portfolio-oriented description; it includes an externally referenced local image and is not an application asset or build input. |
| `docs/whisper历史记录.pdf` | Historical archive (8-page PDF); not parsed as an active architecture authority. |

## Key call and data flows

### A. Runtime transcription path

```text
MainWindow Start button
-> MainWindow.start_recording()
-> TranscriptionController.start(beam, original-language label, selected model path/name)
-> settings.default_settings() + validate_runtime_paths()
-> TranscriptStore(actual outputs directory) + initial config/log/session event
-> TranscriptionEngine.start()
   -> capture thread: sounddevice.InputStream -> ring buffer
   -> worker thread: queued chunk -> resample 48 kHz to 16 kHz
      -> WhisperCppBackend.transcribe_chunk()
         -> temporary PCM WAV -> whisper-cli subprocess -> parsed timestamped raw lines
      -> TranscriptStore.append_raw()
      -> simple_dedup() -> fuzzy_boundary_dedup() -> clean hallucination filter
      -> TranscriptStore.append_clean()
-> engine/controller event callback -> EventBridge Qt signal -> MainWindow.handle_event()
-> transcript tables, session counters, status strip, and in-UI logs update on the UI side
```

The current engine creates one backend in its worker loop and calls the CLI once per queued chunk. The normal UI path only constructs `WhisperCppBackend`; the faster-whisper option remains legacy/support code.

### B. UI/control and thread path

`MainWindow` owns widget state and uses `TranscriptionController` as its session boundary. Start is synchronous only through validation/session initialization; capture and inference are background engine threads. Engine events travel through `EventBridge.event_received`, a Qt signal, before `MainWindow.handle_event()` mutates widgets. Every successful Session has a UUID plus monotonic generation; the controller rejects stale callbacks before state mutation and MainWindow rechecks the identity after queued Qt delivery. A valid newer Session resets displayed Clean/Raw rows, counters, queue display, and the successful-copy cursor, while Stop and Start failure before Session creation preserve the previous display.

Stop is deliberately initiated from `MainWindow.stop_recording()` on a separate `ui-stop-controller` thread because `TranscriptionEngine.stop()` waits for capture closure and queued inference drain. Controller states (`Idle`, `Starting`, `Recording`, `Stopping`, `Error`) decide button/combo enablement. `safe_shutdown()` stops timers, protects dialog shutdown, and either waits for that stop thread or calls controller stop during application exit.

Model selection has two explicit user-facing confirmation surfaces after Step 1B:

```text
MainWindow combo: explicit changed + available selection
-> _on_model_combo_changed()
-> _set_selected_model()
-> MainWindow transient QLabel + reusable single-shot 2 s QTimer

Model Manager: explicit changed + available Select
-> select_current_row()
-> _select_model()
-> dialog transient QLabel + reusable single-shot 2 s QTimer
-> model_selected signal -> MainWindow._set_selected_model()
-> no second MainWindow confirmation
```

The shared `_set_selected_model()` / `_select_model()` state-application paths clear stale confirmation but do not themselves show success. Startup restore, refresh/scan/reload, import auto-selection, verified download-completion auto-selection, unavailable/rejected selection, and repeated same-path selection therefore do **not** show a selection-success confirmation. Rapid explicit selections reuse/restart the same surface timer, so an older timer does not clear a newer message.

### C. Model-management and integrity path

```text
MainWindow -> ModelManagerDialog
  -> scan_model_dirs(default/configured/imported roots)
     -> model_status()
        -> official managed filename: receipt/current-stat status from model_integrity
        -> explicit custom import: local extension/minimum-size validation

Download Model
  -> dialog ensures selected target directory and persists it
  -> daemon worker thread -> model_manager.download_and_publish_model()
  -> model_integrity.execute_model_download()
     -> remove managed stale staging
     -> optional existing-final full verification/reuse
     -> hidden staging directory on target filesystem
     -> vendored downloader subprocess
     -> exact size + SHA-256 validation against model_manifest
     -> os.replace(staged final) + atomic verification receipt
  -> Qt download_finished signal -> rescan -> only available model may be selected
```

`packaging/model_manifest.json` is the authoritative downloadable-model list. The downloader's network result alone is never the availability decision. Imported `.bin`/`.gguf` files are intentionally a separate, local-validation path.

### D. Settings and persistence path

```text
resource_paths.py
  -> source-mode project paths OR frozen-App Resources / user Application Support/Documents paths
  -> settings.py module defaults
     -> model_manager.AppSettings JSON (selected model, CLI, beam, model roots/imports/download root, output base, UI language)
     -> TranscriptionSettings for a newly started session
        -> config.json in that session
```

`AppSettings` persists model-related selection, default beam, `output_base_dir`, and `ui_language` at `APP_SETTINGS_PATH`. MainWindow exposes both choices; changing UI language retranslates live widgets while remaining independent from `Original Language` and its whisper CLI code. Controller startup passes the selected base through `default_settings()`, which resolves the actual `TranscriptionSettings.output_root` as `<base>/outputs`.

Current `validate_runtime_paths()` preflights beam/language/task, `whisper-cli`, selected model, and output-root writability before the controller creates `TranscriptStore`; an invalid output base therefore fails before a partial session is created.

### E. Session and evidence path

```text
controller.start()
-> TranscriptStore(settings.output_root)
-> <actual-outputs-dir>/<timestamp>/
   -> raw.txt          (engine appends parsed backend evidence)
   -> clean.txt        (engine appends conservative dedup/filter result; current Session may rename or recover it)
   -> session.log      (controller/engine lifecycle and error records)
   -> config.json      (settings snapshot written at session creation)
-> engine.stop() drains queued work, logs Stop complete, then closes all handles
```

The Clean writer continues appending to the same inode after a current-Session rename. If that inode conclusively has no `.txt` path in the verified original Session, recovery copies its exact flushed history to a no-clobber file and, while active, switches later appends to the verified new writer; Stop preserves an exact snapshot for the same operation. A new Session always creates its own initial `clean.txt`. The UI path buttons follow only the Store's currently verified path.

The Store owns directory creation, open handles, append counters, flushes, current-writer identity, rename/recovery and close. The Controller owns Session creation and ID + generation ownership; the engine owns continued evidence writes while running; the UI owns no independent file authority. A completed Session is normally immutable, but an explicit post-Stop Rename or full-history recovery may rename the verified writer or create a new current Clean `.txt`. No persistent current-Clean locator exists across App restart yet. Future LLM/Session Browser work must first implement a trusted resolver or manifest and must fail closed if identity cannot be proven; scanning a directory and choosing an arbitrary `.txt` is not acceptable.

### F. Build, package, and Release path

The REL1B candidate precedes future real packaging with this separate flow:

```text
protected release_controller status|integrate|resume
-> release_approval: independent signature/config/contracts/review/owner/ref/path binding
-> release_journal: durable intent (never execution authority)
-> release_integration: audited isolated clone -> exact fetch -> feature push -> divergent merge
-> absent ignored environment -> original pinned bootstrap -> memory-only environment/source proof
-> clone-local Python 3.12.14 + full strict tests -> proof/approval/clean/refs recheck
-> ordinary main push -> exact remote ref reconciliation
```

Production trust/entry deployment is only a proposed fixed-root scheme awaiting
Human decision. The repository entry fails closed without it. Tests restrict a
Python-only fixture policy to newly created Downloads repositories/local bare
remotes and an independent fixture namespace; no production CLI switch enables
it. Resume after environment creation stops because no journal establishes its
trusted origin. Main already present without trusted completion enters Human
reconciliation without repeat push or rollback. See `PACKAGING.md` for precise
interfaces and current SSH/HTTPS authentication isolation limits. This legacy
entry does not accept the entire Step 1 or perform real production integration.
The separate workflow entry composes Integration -> independent final-main
receipt -> BuildController -> exact-artifact Human receipt -> signed publication
plan -> Publisher. Its candidate release/asset recovery additionally requires
external exact-ID reconciliation; deployment/authentication remain unavailable.

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
   -> scripts/bootstrap_python_env.sh
      -> pinned uv + Python + uv.lock -> .venv
   -> scripts/bootstrap_whisper_runtime.sh
      -> manifest-derived CMake + pinned external/whisper.cpp -> CLI/dylibs
   -> PYTHON=.venv/bin/python scripts/build_macos.sh
      -> package_runtime validate-sources
      -> build_app_icon (tracked PNG -> generated ICNS)
      -> PyInstaller Release spec (ui_app.py + manifest data + generated icon)
      -> package_runtime normalize-app
      -> ad-hoc codesign
      -> verify_packaged_runtime
      -> release_identity write-build-provenance
      -> dist/ClassroomTranscriber.app

.venv/bin/python scripts/build_release_zip.py --version 1.1.0 \
  --expected-source-commit <commit> --task-root <Downloads-managed-root> \
  --artifact <task-root/artifacts/release.zip> \
  --human-review-extraction <task-root/human-review>
-> clean expected source + formal-Python + canonical manifest/App/provenance checks
-> verify source App -> archive only App -> extract under the managed task root
-> compare bundle structure/bytes/modes/symlinks -> verify extracted App
-> atomically publish the no-clobber ZIP and retain the verified extraction
```

The ignored `external/whisper.cpp` is a build input reconstructed by bootstrap, not a tracked source dependency to copy. The resulting App bundles CLI/dylibs, the vendored downloader, model-integrity manifest, and generated ICNS; it deliberately does not bundle model binaries or user settings.

## Contract-sensitive zones

| Zone | Why it is sensitive in this codebase | Owning files | First regression checks after a change |
| --- | --- | --- | --- |
| Stable ASR scheduling and clean output | Chunk cadence, ring-buffer alignment, resampling, parser behavior, dedup, and filtering jointly determine transcript content and timing. The static contract freezes this path for Product Polish. | `transcription_engine.py`, `stream_transcribe.py`, `settings.py` | Dedup/pseudo-real suites, `test_ui_support.py`, `test_backends.py`; real ASR acceptance if the Runtime boundary moves. |
| Qt main-thread boundary and Stop behavior | Capture/inference are background threads; widget mutation is signal-routed; Stop waits for microphone close and queued work. Blocking/misrouting can freeze the UI or lose final evidence. | `ui_app.py`, `transcription_controller.py`, `transcription_engine.py` | `test_ui_support.py` final-partial/queue/Stop cases; targeted UI smoke for model/dialog changes. |
| Microphone lifecycle | `sounddevice.InputStream` is opened in capture thread and must close before delayed work drains; second Start depends on clean state reset. | `transcription_engine.py`, controller/UI stop/shutdown paths | `test_ui_support.py` queue/Stop cases and manual Start -> Stop -> Start acceptance when lifecycle code changes. |
| Evidence layer | Raw is preserved before clean dedup/filtering, configuration is written at creation, and file handles close only after Stop drain. | `transcript_store.py`, controller, engine, `settings.py` | `test_ui_support.py` store/config cases; a session filesystem check for any creation/path/lifecycle change. |
| Model integrity transaction | Availability is receipt-backed after exact-size/SHA validation, staging, and atomic publish; dialog state must not bypass it. | `model_integrity.py`, `model_manager.py`, `ui_app.py`, `model_manifest.json` | `test_model_integrity.py`, `test_model_manager_ui_contract.py`, `test_model_download_resources.py`. |
| Settings/resource split | Source versus frozen mode resolves different resource and writable paths; app settings and session config have distinct scopes. | `resource_paths.py`, `settings.py`, `model_manager.py`, controller | `test_ui_support.py`, `test_model_download_resources.py`; packaging tests if a bundled resource changes. |
| Packaged Runtime closure | Manifest-driven resource collection, dylib/RPath normalization, signing, and bundled/isolated smoke form a fail-fast chain. A valid UI alone is insufficient. | runtime manifest, specs, bootstrap/helper/build/package/verifier scripts | `test_runtime_manifest.py`, `test_whisper_runtime_bootstrap.py`, `test_build_orchestration.py`, `test_packaged_runtime.py`; formal build/verifier for implementation changes. |
| Packaged App icon | A tracked approved source must produce the ICNS referenced by `Info.plist`, survive signing and ZIP round-trip, and never depend on an external developer path. | `packaging/icons/ClassroomTranscriber.png`, runtime manifest, icon generator, Release spec/build/verifier | `test_app_icon.py`, `test_runtime_manifest.py`, `test_packaged_runtime.py`, `test_release_zip.py`; formal App/ZIP verification. |
| Release ZIP closure | Release script rejects wrong/dirty source, noncanonical or stale manifest/App/provenance inputs, unsafe contents, targets outside the explicit Downloads task root, and existing targets; it then validates a complete round trip and retains the verified App extraction before atomic no-clobber ZIP publication. | `release_identity.py`, `build_release_zip.py`, runtime verifier, release contract/manifest fields | `test_release_identity.py`, `test_release_zip.py`, plus a future real formal 1.1.0 App/ZIP flow. |
| Integration authorization and environment provenance | External approval and actual Git facts must precede each mutation. Version reports and journal hashes cannot trust ignored code; only this invocation's fresh pinned bootstrap/full suite can gate main. | Four `release_*` control modules; independent external trust and managed Downloads paths | Three `test_release_*` control suites plus a separate full-source real-gate smoke; no production trust installation or real remote mutation. |

## Product Polish architecture impact index

This is an impact index for the targets already defined in Product Polish static/runtime. It records present ownership and regression boundaries only; it does not prescribe a future class, property, widget, or implementation shape.

| Product Polish target | Likely ownership / relevant modules | Important boundaries | Regression areas |
| --- | --- | --- | --- |
| **1A Current-model readability** | `ui_app.py` current label/combo/dialog summary; `model_manager.py` `ModelInfo` display properties; UI/model tests. | Step 1A separates concise `current_summary_label` (`name | size | status`) for current-model summaries from the full `display_label` retained by combo/log paths. Full path remains available through both summary tooltips and the independent Model Manager Path column. Model availability/selectability remains separate. | `test_ui_support.py`, `test_model_manager_ui_contract.py`, model discovery/selection smoke. |
| **1B Model selection transient confirmation** | `ui_app.py` explicit selection entrypoints in MainWindow/ModelManagerDialog, each surface's transient label/timer, shared model state setters, `AppSettings` persistence; model UI tests. | Step 1B confirmation is event-source-sensitive: only explicit changed + available selection confirms. Shared state setters clear stale feedback but do not show it; startup/refresh/scan/reload, import/download auto-selection, unavailable/rejected selection, and repeated same-path selection do not confirm. Model Manager propagation produces no duplicate MainWindow confirmation. | `test_model_manager_ui_contract.py`, `test_ui_support.py`, model regressions, targeted/offscreen Qt timer smoke, manual source UI smoke. |
| **1C Download visible progress/busy feedback** | `ModelManagerDialog` download state, indeterminate `QProgressBar`/status label, background worker, Qt completion signal; model manager/integrity modules. | Explicit download shows the model name and busy state until success/failure cleanup. Network download and SHA validation remain off the Qt main thread; only verification may yield an available/selectable official model. | `test_model_integrity.py`, `test_model_manager_ui_contract.py`, `test_model_download_resources.py`, targeted success/failure dialog-state smoke. |
| **1D Configurable output root** | `resource_paths.py`, `settings.py`, `model_manager.AppSettings`, controller start, UI; `TranscriptStore` as unchanged evidence owner. | Persisted `output_base_dir` is mapped to `<base>/outputs` before store creation; writability is validated before a session exists. Historical sessions and evidence semantics remain unchanged. | `test_output_root.py`, `test_ui_support.py`, controller/store regressions, packaged smoke. |
| **1E Chinese / English UI switch and semantic alignment** | Persisted `AppSettings.ui_language`, `settings.py` normalization/labels, `ui_app.py` `TEXT`/`tr` and live retranslation. | UI language is distinct from `Original Language` and whisper command `-l`; switching retranslates MainWindow/Model Manager surfaces without changing ASR/model/output settings. | `test_ui_language.py`, `test_ui_support.py`, `test_model_manager_ui_contract.py`, targeted offscreen bilingual smoke. |
| **1F Packaged App icon** | Tracked icon source, Manifest contract, icon generator, Release spec/formal build, packaged/release verifier. | Formal build derives ICNS from the repo-owned PNG, PyInstaller writes it and `CFBundleIconFile`, and the shared verifier gates both source and ZIP-extracted Apps. Generated iconset/ICNS remain ignored; no developer absolute path enters the contract. | `test_app_icon.py`, `test_runtime_manifest.py`, `test_packaged_runtime.py`, `test_release_zip.py`, formal App build/verifier and ZIP round-trip. |
| **1G Packaged regression / acceptance** | All prior touched UI/settings/packaging modules; build wrapper, Runtime verifier, Release ZIP process. | Must verify the packaged App rather than infer success from source-run UI; preserve ASR, integrity, evidence, and Runtime closure contracts. | Formal one-entry build, packaged verifier, model workflow, Start/Stop/second Start, evidence files, and relevant test groups above. |

After Step 1A, the model-presentation boundary is explicitly split: concise current-model summaries use `ModelInfo.current_summary_label`, while combo and diagnostic log paths continue to use the full `display_label`; path detail remains available through tooltips/table. After Step 1B, transient selection feedback is explicitly owned by the two user-action entrypoints and their parent-owned timer/label state, rather than by generic model setters or restoration paths. Steps 1C-1E add UI feedback, a persisted output base, and a persisted live UI-language selection without changing ASR/evidence/integrity semantics. Step 1F adds only the manifest-driven icon generation and package-verification path described above.

## Observed documentation/source alignment notes

These notes are observations from the baseline, not requests to change unrelated tracked files during Repo Map work.

1. `packaging/runtime_manifest.json` still records several observed compatibility statuses as pending clean-machine E2E, while `docs/deployment_runtime.md` records Deployment Steps 8/9 and M4 Max/M5 ordinary-user acceptance as PASS. The manifest's frozen build/component data is actively consumed by code; its observed acceptance-status metadata appears historically lagged relative to the deployment runtime.
2. `PACKAGING.md` now distinguishes completed historical 1.0.0 clean-machine acceptance from the still-future gate for exact 1.1.0 App/ZIP bytes; it does not treat the historical result as acceptance of the unbuilt, unpublished 1.1.0 candidate.
3. The historical Deployment UX backlog says the current-model path cannot be accessed in full. Current `ui_app.py` sets full-path tooltips on both current-model summaries; the Model Manager table independently exposes Path. The Product Polish runtime's more precise description matches current source better.
4. The legacy `run_long_test.sh` contains a machine-specific path, unlike the formal build scripts' repo-relative design. It is not part of the formal developer-build or Release path.

## Unknown / not established by the static scan

- This map does not independently reproduce microphone or Metal acceptance; those PASS claims are recorded in deployment runtime evidence.
- Step 1B's implementation received targeted automated/offscreen Qt checks and later manual source-UI acceptance, but this map itself is not execution evidence.
- No tracked module implements the planned LLM sidecar, session browser, or persistent backend; planning documents are not implementation evidence.
- The intended ongoing maintenance status of `run_long_test.sh` beyond its observable legacy behavior is not established.

## Repo Map maintenance policy

Every implementation-Step review performs a **Repo Map impact check**.

Update this map when a change normally affects one or more of the following:

- an engineering file is added, deleted, or renamed;
- module responsibility, call structure, public interface, or ownership boundary changes;
- important state, persistence, filesystem, network, subprocess, or UI-thread side effect is introduced or moved;
- settings schema or data flow changes;
- build, package, Runtime, or Release pipeline changes;
- a major test ownership or production-coverage relationship changes.

Normally no update is needed for local wording, layout-only adjustment, helper-internal work that leaves module responsibility/interfaces/data flow unchanged, or a fix that restores an existing contract without a structural change. In that case, a later review may record:

```text
Repo Map impact: NONE
```

Do not manufacture a Repo Map diff for every commit. When an update is needed, keep it architectural: record new ownership, dependency, side-effect, and regression impact rather than copying implementation detail or turning a design choice into a new frozen contract.
