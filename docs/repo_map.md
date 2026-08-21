# Classroom Live Transcriber — Repository Map

## Document identity and authority

| Field | Value |
| --- | --- |
| Repository | `smter6626/live_subtitle_generator` (Classroom Live Transcriber) |
| Branch | `main` |
| Structural baseline | Original full scan at `4d2059d273d0ba94373b1969b8236ef462b6acae`; affected ownership/flows updated through Product Polish Step 1F |
| Updated | 2026-08-21 |
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
| Release artifact creation and validation | `scripts/build_release_zip.py` |
| Contract and regression coverage | `testCodes/` |
| Governance, current state, user/build documentation | `docs/`, `README.md`, `PACKAGING.md` |

## File and module map

### Runtime application modules

| Path | Responsibility and important interface | Dependencies / primary users | State, side effects, and likely change impact |
| --- | --- | --- | --- |
| `ui_app.py` | PySide6 entry point (`main`), `MainWindow`, `ModelManagerDialog`, `TranscriptTable`, translation lookup, and `EventBridge`. Owns visible controls, transcript/log widgets, dialog lifecycle, Start/Stop requests, UI refresh, transient model-selection feedback, model-download busy feedback, output-base choice, and live UI-language switching. | Uses `TranscriptionController`, model-manager functions, settings constants, transcript parsers, crash logging. It is the PyInstaller entry. | Persists model/beam/output-base/UI-language choices through `AppSettings`; opens Finder with `open`; starts a non-Qt stop thread; receives worker events through a Qt signal. Explicit user actions own transient feedback while generic state restoration does not. Changes can affect UI responsiveness, controller state gating, persistence, transcript display, and UI contract tests. |
| `transcription_controller.py` | Session state machine (`EngineState`) and public `start(...)` / `stop()`. Creates normalized runtime settings, validates them, creates the session store, then owns the engine instance. Converts engine events to controller/UI events. | Uses `default_settings` and `validate_runtime_paths`, `TranscriptStore`, `TranscriptionEngine`; constructed by `MainWindow`. | Owns in-memory state, current settings/store/engine. Creates a session before starting capture and emits its file locations. A change can alter Start/Stop semantics, error transitions, evidence initialization, and UI event behavior. |
| `transcription_engine.py` | Stable live-ASR implementation: capture loop, worker loop, 48 kHz capture / 16 kHz resample, 10 s chunks with 3 s overlap, final partial handling, clean-layer hallucination filter, queue events, and `stop()` drain/close behavior. | Uses `sounddevice`, `numpy`, `TranscriptionSettings`, `WhisperCppBackend` and dedup/resample helpers from `stream_transcribe.py`, and `TranscriptStore`. Created only by the controller. | Owns audio ring buffer, task queue, worker/capture threads, stop event, prior clean text. Opens the microphone; creates temporary WAVs indirectly through the backend; invokes subprocess inference; appends evidence and emits events. Changes have high ASR, microphone, evidence, timing, and UI-thread impact. |
| `stream_transcribe.py` | Shared ASR helpers: exact/fuzzy boundary dedup, resampling, PCM WAV writer, whisper.cpp command creation/output parsing, and `WhisperCppBackend`. It also retains a separate legacy console streaming runner and optional `FasterWhisperBackend`. | Imported by settings and the production engine; directly exercised by ASR tests. The standalone `main()` is not the normal UI path. | `WhisperCppBackend.transcribe_chunk()` creates a temporary WAV and runs `whisper-cli`; legacy `main()` opens a microphone and appends timestamped root-level raw/clean files. Editing shared helpers affects both UI runtime and legacy CLI/regression cases. |
| `transcript_store.py` | Creates one timestamp-named session directory; writes/flushes `raw.txt`, `clean.txt`, `session.log`, and `config.json`; parses displayable transcript lines. | Uses `settings.write_config_json`; used by controller, engine, UI, and tests. | Owns open file handles and evidence-file lifecycle. `TranscriptStore(output_root)` treats its argument as the actual `outputs` directory and creates `<output_root>/<timestamp>/...`. Any change can break evidence semantics, Stop finalization, or session tooling. |
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
| `scripts/bootstrap_and_build.sh` | Formal one-entry build orchestrator. | Requires macOS arm64; calls the Python bootstrap, Runtime bootstrap, then injects `.venv/bin/python` into the Release build; checks the produced `.app`. | The main developer-build boundary. `test_build_orchestration.py`, packaging/runtime tests. |
| `scripts/bootstrap_python_env.sh` | Creates or, with `--recreate`, removes/rebuilds the project `.venv` from pinned uv/Python/lock metadata. | Downloads and SHA-checks uv when needed; writes ignored `.tools/` and `.venv/`; runs environment contract tests. | Dependency lock, formal interpreter, and destructive recreate behavior are sensitive. `test_python_environment.py`, `test_runtime_manifest.py`. |
| `scripts/bootstrap_whisper_runtime.sh` | Rebuilds or verifies (`--verify-only`) the pinned ignored whisper.cpp Runtime. | Uses manifest values through `whisper_runtime_contract.py`; may download CMake and clone/build `external/whisper.cpp`; refuses dirty/unexpected third-party state. | Controls third-party Runtime provenance and generated binary closure. `test_whisper_runtime_bootstrap.py`, `test_runtime_manifest.py`. |
| `scripts/whisper_runtime_contract.py` | Manifest reader and source-Runtime verifier; commands: `get`, `cmake-arguments`, `artifact-records`, `verify-runtime`. | Reads `runtime_manifest.json`; invokes Git, `file`, `otool`, and the CLI smoke during verification. | Centralizes build-profile/data interpretation. Do not duplicate manifest facts in bootstrap code. Bootstrap/manifest tests protect it. |
| `scripts/build_app_icon.py` | Manifest-driven macOS icon generator. | Validates the tracked source SHA/canvas, removes its edge-connected light matte, renders a 1024 px RGBA master and complete iconset with locked PySide6/NumPy, then calls macOS `iconutil`; writes only ignored temporary/`build/` output. | Reproducible icon quality and generated ICNS boundary. `test_app_icon.py`, manifest/packaging tests. |
| `scripts/build_macos.sh` | Formal Release App build and hard gate. | Validates sources, deletes generated `build/` and `dist/`, generates the Manifest App icon, runs PyInstaller, normalizes App Runtime, ad-hoc signs, then verifies. | Build success semantics and generated artifacts. `test_app_icon.py`, `test_packaged_runtime.py`, `test_build_orchestration.py`. |
| `scripts/build_macos_debug.sh` | Separate console/debug PyInstaller build. | Deletes its generated debug outputs and applies permissive debug RPath adjustments. | Not the formal Release gate; changes should be checked against the Debug spec and manual debug use. |
| `scripts/package_runtime.py` | Manifest-driven source preflight and post-PyInstaller App Runtime normalizer; subcommands `validate-sources` and `normalize-app`. | Reads manifest and model contract; modifies copied App binaries with `install_name_tool`, permissions, and resource checks. | High-risk package closure boundary; `test_packaged_runtime.py`. |
| `scripts/verify_packaged_runtime.py` | Read-only packaged-App verifier. | Checks the Manifest App icon resource/ICNS structure/`CFBundleIconFile`, required Runtime files, arm64, RPaths/dependency closure, downloader/model manifest, codesign, bundled CLI smoke, and isolated Runtime smoke. | Formal build and Release ZIP trust boundary; `test_packaged_runtime.py` and `test_release_zip.py`. |
| `scripts/build_release_zip.py` | Formal Release ZIP entry (`--version` required). | Requires formal Python, macOS arm64, clean Git source, and a verified App; writes a staged/final ZIP under `dist/`, extracts outside the repo, compares bytes/modes/symlinks, and re-verifies. | Release payload and provenance boundary. `test_release_zip.py`. |
| `scripts/clean_build.sh` | Developer cleanup tool. | Deletes generated `build/`, `dist/`, and selected caches while preserving models, outputs, external Runtime, and historical `venv/`. | Destructive only for generated locations; not called by formal build. |
| `run_long_test.sh` | Legacy long-running console transcription and system-monitoring helper. | Starts the legacy stream runner, writes ignored test-run logs, samples macOS system tools, and contains a machine-specific developer path. | It is not portable and not part of the formal build/release path; its current maintenance status is not established by source. |

### Manifests, specs, dependency files, and vendor material

| Path / group | Responsibility | Used by / change impact |
| --- | --- | --- |
| `packaging/runtime_manifest.json` | Machine-readable frozen Runtime/build/bundle/release contract plus observed/pending metadata. Enumerates the seven required Runtime components, vendored downloader, model-manifest location, App-icon source/hash/generated/bundle paths, formal build entry, and release filename template. | Consumed by bootstrap/icon helpers, PyInstaller specs, Runtime normalizer/verifier, Release ZIP code, and manifest tests. It is the packaging data source of truth. |
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
| `test_release_zip.py` | `build_release_zip.py` and packaged verifier handoff | Explicit version/locked Python/clean source, deterministic ZIP round-trip including ICNS bytes, payload exclusions, path/symlink safety, verifier failure handling, and reported digest. |

### Documentation and historical material

| Path / group | Current role in this repository map |
| --- | --- |
| `docs/product_polish_static.md`, `docs/product_polish_runtime.md` | Current Product/UX stable contract and execution state. This Repo Map reflects source through the Step 1B implementation commit; ACTIVE-step state remains owned by runtime. |
| `docs/deployment_static.md`, `docs/deployment_runtime.md` | Deployment/release stable contract and recorded execution evidence; Deployment currently has no ACTIVE step. |
| `README.md`, `PACKAGING.md` | User/developer navigation and packaging explanation. Treat current code and manifests as implementation truth where their wording differs. |
| `docs/工程细节.md` | Detailed explanatory engineering narrative; useful orientation, but secondary to current source/manifests/static/runtime. |
| `docs/LLM_POSTPROCESSING_DESIGN.md`, `docs/LLMsteps.md`, `docs/goalForNextLevel.md`, `docs/user_understand.md` | Design/backlog material for an LLM sidecar and later directions. It does not describe a tracked LLM implementation on current `main`. |
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

`MainWindow` owns widget state and uses `TranscriptionController` as its session boundary. Start is synchronous only through validation/session initialization; capture and inference are background engine threads. Engine events travel through `EventBridge.event_received`, a Qt signal, before `MainWindow.handle_event()` mutates widgets.

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
   -> clean.txt        (engine appends conservative dedup/filter result)
   -> session.log      (controller/engine lifecycle and error records)
   -> config.json      (settings snapshot written at session creation)
-> engine.stop() drains queued work, logs Stop complete, then closes all handles
```

The store owns directory creation, open handles, append counters, flushes, and close. The controller owns session creation; the engine owns continued evidence writes while running; the UI owns only current-session paths for Finder reveal and display. No tracked component moves or rewrites a completed session.

### F. Build, package, and Release path

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
      -> dist/ClassroomTranscriber.app

.venv/bin/python scripts/build_release_zip.py --version <version>
-> clean source + formal-Python checks
-> verify source App -> archive only App -> extract outside repo
-> compare bundle structure/bytes/modes/symlinks -> verify extracted App
-> dist/ClassroomTranscriber-<version>-macOS-AppleSilicon.zip
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
| Release ZIP closure | Release script rejects dirty source and unsafe contents, then validates a round trip and extracted App Runtime. | `build_release_zip.py`, runtime verifier, release manifest fields | `test_release_zip.py` plus actual formal Release ZIP flow when release code/specs change. |

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
2. `PACKAGING.md` retains a “Work still pending” paragraph saying clean-machine acceptance/real transcription E2E has not yet occurred, while `docs/deployment_runtime.md` records those acceptances as complete. This is documentation-state drift, not a source implementation discrepancy.
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
