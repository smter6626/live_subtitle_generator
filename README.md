# Classroom Live Transcriber

English | [简体中文](README.zh-CN.md)

Classroom Live Transcriber is a local, near-real-time classroom transcription app for macOS on Apple Silicon. It uses `whisper.cpp` with Metal acceleration and keeps microphone transcription on your Mac.

```text
Microphone -> local Whisper transcription -> live transcript UI -> session files
```

The current transcription path does not depend on a cloud LLM. Release 1.0.0 does not include an LLM summary, translation sidecar, semantic rewrite, or note-taking service.

## Features

- Start and stop classroom transcription from a PySide6 desktop interface
- Local `whisper.cpp` inference with the Metal backend
- Clean Transcript and Raw Transcript views
- Model Manager for model download, import, selection, and download location
- Exact-size and SHA-256 integrity verification for official model downloads
- Visible busy/progress feedback while a model is downloading
- Configurable output location
- Chinese and English interface languages
- Main-window height bounded to the current screen, with an independently scrollable controls column
- A Session-owned Clean toolbar for no-clobber rename, incremental text copy, Finder reveal, and absolute-path copy
- Full-history Clean recovery when the current writer conclusively has no `.txt` path in its original Session
- Separate Original Language selection for English, Chinese, Japanese, French, Spanish, German, Korean, or Auto Detect audio
- Beam control from 3 to 8, with a default of 5
- Persistent model, Beam, interface language, model location, and output settings
- Timestamped session evidence files
- A custom macOS app icon in the packaged release

## Download

The current formal release is **1.0.0**:

- [Classroom Transcriber 1.0.0 GitHub Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0)
- Release asset: `ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip`

Version 1.1.0 is an unbuilt, unpublished candidate on `codex/release-1-1-0-automation`. Its fixed candidate title is **Classroom Transcriber 1.1.0**, and its intended asset is `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip` containing `ClassroomTranscriber.app`. The downloadable 1.0.0 App does not contain these candidate changes. Prior clean-machine acceptance of 1.0.0 remains historical evidence only; it does not accept any new 1.1.0 App or ZIP bytes.

Ordinary users do **not** need to clone this repository, install Python, or compile `whisper.cpp`. Whisper models are not included in the ZIP; download or import one from Model Manager after opening the app.

## System Requirements

- A Mac with Apple Silicon (`arm64`)
- macOS; release acceptance was completed on Apple M4 Max and Apple M5 machines running macOS 27 Beta
- Permission to use the microphone
- Enough free disk space for the selected model and its temporary download staging
- An internet connection while Model Manager downloads a model

The project has not validated Intel Macs, Windows, M1/M2/M3 hardware, or older macOS versions. A minimum macOS version has not been established.

## Quick Start

No Terminal commands are required.

1. Download `ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip` from the [1.0.0 Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0).
2. In Finder, double-click the ZIP to extract `ClassroomTranscriber.app`.
3. Open `ClassroomTranscriber.app`.
4. The release is not notarized. If macOS says Apple cannot verify the app, close the warning, open **System Settings → Privacy & Security**, choose **Open Anyway**, authenticate if asked, and open the app again.
5. When macOS requests microphone access—normally when recording starts for the first time—allow it.
6. Click **Manage Models** to open Model Manager.
7. Use **Download Model** or **Import Existing Model**. Wait for a downloaded model to finish verification and show `available`, then select it if necessary.
8. Choose **Interface Language**: `中文` or `English`.
9. Choose **Audio / Original Language**: `English`, `Chinese`, `Japanese`, `French`, `Spanish`, `German`, `Korean`, or `Auto Detect`.
10. Leave **Beam Size** at its default of `5` unless you have a reason to change it.
11. If desired, use **Choose Output Location** to select where future sessions will be stored.
12. Click **Start Recording**. The Clean Transcript view will update after the first audio chunk has been processed.
13. Click **Stop Recording** when the class or recording is finished. The app stops capture and finishes audio already submitted for processing.
14. If you are running the current feature branch, use the Clean file actions below. These controls are not present in the downloadable 1.0.0 app.

### Clean file actions on the current feature branch

- **Reveal Clean** and **Copy Clean Path** share one compact row in the left controls. Each use rechecks that the path still identifies the current Session's Clean writer. If verification fails, Finder and the clipboard remain unchanged.
- **Rename Clean TXT** is at the left of the Clean table toolbar. Enter only a filename stem; the app owns the fixed `.txt` suffix. A normal rename is no-clobber, preserves the writer inode, and works while recording or after Stop.
- If a complete check proves that the writer has no regular `.txt` path in its verified original Session, the app asks whether to create the requested name from the complete Clean history. **Yes** creates a no-clobber file containing all Clean bytes up to the switch; during active recording, later appends go only to the new file. **No** or cancel creates and switches nothing. The prompt warns that an open file handle does not guarantee a durable path after close or app exit.
- Permission errors, uncertain inspection, or an unsafe/replaced Session directory are not treated as a missing file. The action stops with an error and does not offer recovery.
- **Copy New Text**, immediately left of **Jump to Live**, copies all displayed Clean rows on its first successful use. Later uses copy only rows added after the previous successful copy.
- Starting a new Session clears the displayed Clean/Raw rows and resets the incremental-copy cursor. All Clean file actions then belong to the new Session; the stopped previous Session is no longer the UI target.

If the screen is not tall enough to show every control, scroll the left controls/session column with its scrollbar, mouse wheel, trackpad, or keyboard focus traversal. The status strip stays visible above it, and Clean Transcript, Raw Transcript, and Logs keep their own independent scrolling.

## Model Manager

Open **Manage Models** from the main window. Model Manager provides:

- **Download Model** — download one of the manifest-backed official models
- **Import Existing Model** — use an existing `.bin` or `.gguf` model in place
- **Select Model** — make an `available` model the current model
- **Download Location / Choose Folder** — change where future model downloads are stored
- A model table showing name, size, path, and availability/integrity status

The default download location is:

```text
~/Documents/ClassroomTranscriber/models
```

Official downloads are written to a hidden staging directory first. A model becomes `available` only after its exact size and SHA-256 pass the integrity check and it is published to the final path. A busy indicator and the current model name remain visible during the download. Invalid, partial, or unverified official downloads are not selectable as available models. Explicitly imported custom models use the app's separate local import checks.

The downloadable list and exact sizes come from [`packaging/model_manifest.json`](packaging/model_manifest.json):

| Model | Exact bytes | Approx. displayed size | Practical starting point |
| --- | ---: | ---: | --- |
| `large-v3` | 3,095,033,483 | 2.9 GB | Multilingual, quality-first option; largest download |
| `large-v3-turbo` | 1,624,555,275 | 1.5 GB | Smaller multilingual large-model variant |
| `medium.en` | 1,533,774,781 | 1.4 GB | English-only model |
| `small.en` | 487,614,201 | 465.0 MB | Smaller English-only model for a quicker trial |
| `base.en` | 147,964,211 | 141.1 MB | Smallest downloadable English-only trial model |

Model quality, speed, and memory use depend on the Mac, audio, language, and model. The project does not publish benchmark percentages for these choices.

## Interface Language vs. Original Language

These settings are independent:

- **Interface Language** changes the app's visible controls and messages between Chinese and English.
- **Audio / Original Language** tells Whisper what language is mainly present in the microphone audio.

The two Interface Language choices are the application's UI locales; they do not limit
the available Audio / Original Language choices.

The Original Language choices are:

- `English` → Whisper language `en`
- `Chinese` → Whisper language `zh`
- `Japanese` → Whisper language `ja`
- `French` → Whisper language `fr`
- `Spanish` → Whisper language `es`
- `German` → Whisper language `de`
- `Korean` → Whisper language `ko`
- `Auto Detect` → Whisper language `auto` (automatic language detection)

`Auto Detect` is the canonical automatic-language choice. Existing saved selections
using `Mixed Chinese/English`, `中英混合`, `mixed`, or `auto` remain compatible and
normalize to `Auto Detect`.

English-only `.en` models, such as `medium.en`, `small.en`, and `base.en`, accept
only `English` (`en`). Select a multilingual model for every other listed Original
Language choice, including `Auto Detect`; incompatible `.en` combinations are rejected
instead of falling back to English.

Changing Interface Language does not change the ASR Original Language, model, Beam, or transcript contents.

## Beam

Beam controls the amount of search used during transcription. The current range is `3` through `8`, and the default is `5`.

Most users should keep the default. A higher value may increase search work and processing time; it does not guarantee a better transcript for every recording.

## Output Location and Session Files

For the packaged app, the default output base is:

```text
~/Documents/ClassroomTranscriber
```

Every session is stored under an `outputs` directory:

```text
<chosen-root>/outputs/<timestamp>/
├── raw.txt
├── clean.txt                 # initial current Clean name
├── session.log
└── config.json
```

- `raw.txt` — original timestamped transcript evidence from the backend
- `clean.txt` -- the initial name of the current Clean transcript. On the feature branch, Rename Clean TXT may change it to a user-named `.txt` while preserving contents and continued appends, or may recover the complete writer history into a new no-clobber `.txt` when the original Session path is conclusively unavailable. Do not assume that every completed feature-branch Session still has a file literally named `clean.txt`.
- `session.log` — session, chunk, backend, warning, error, and stop events
- `config.json` — the model, language, Beam, paths, and audio configuration for that session

Choosing a new Output Location changes the base for future sessions only. It does not move or rewrite earlier sessions. The structure remains `<chosen-root>/outputs/<timestamp>/`, not `<chosen-root>/<timestamp>/`.

## Privacy and Local Processing

- Microphone transcription and `whisper.cpp` inference run locally on the Mac.
- Session transcripts are saved under the output location you choose.
- Model downloads access the upstream `ggerganov/whisper.cpp` model repository over the network.
- Release 1.0.0 does not send transcripts to a cloud LLM for summary, translation, or semantic rewriting.

These statements describe the current application path; they are not a claim about the behavior of macOS, your network, or third-party software on the computer.

## Troubleshooting

### macOS will not open the app

The current release is not notarized. After the verification warning appears, go to **System Settings → Privacy & Security → Open Anyway**, authenticate if requested, and launch the app again. The verified release acceptance did not require Terminal workarounds.

### No model is available, or Start Recording is disabled

Open **Manage Models**. Download or import a model, wait until its status is `available`, and select it. An official model with `integrity unverified` or `integrity invalid` is not available for Start.

### A model download takes a long time

Large models contain several gigabytes. Keep Model Manager open and watch the busy indicator and model name. Download time depends on the selected model and connection; the current UI intentionally shows activity rather than an estimated percentage.

### Microphone access is missing

Open **System Settings → Privacy & Security → Microphone** and allow ClassroomTranscriber to use the microphone, then return to the app and start again.

### The Output Location is not writable

The app checks the actual `<chosen-root>/outputs` directory before creating a session and reports an error instead of silently switching locations. Choose a folder you can write to with **Choose Output Location**, then start again.

### Model download or integrity verification fails

Check the network connection, available disk space, and selected Download Location, then retry **Download Model**. A failed or partial download remains unavailable; retry uses the managed download transaction again. You can also choose another writable Download Location or import an existing valid model.

### Finding session output

After Start creates a session, click **Open Output Folder**. The main window also displays the active session path. By default it is under `~/Documents/ClassroomTranscriber/outputs/<timestamp>/`.

### Reveal Clean or Copy Clean Path does nothing

On the feature branch, these actions deliberately leave Finder or the clipboard unchanged when the Store cannot prove which Session-local `.txt` is the current writer. Retry after external file activity has stopped. If the path is conclusively absent, use **Rename Clean TXT** to choose whether to create a full-history recovery file.

### Clean rename reports that the destination exists

Rename and recovery never overwrite an existing file, directory, symlink, or same-name decoy. Choose a different filename stem or move the conflicting entry yourself after confirming what it contains.

### Clean rename reports that the source cannot be verified

Permission, I/O, Session-directory identity, or file-type uncertainty fails closed. The app does not reinterpret uncertainty as a missing file and does not offer the **Yes** recovery path until absence has been proven safely.

## Known Limitations

- The downloadable 1.0.0 artifact is macOS Apple Silicon only. There is no Intel Mac or Windows release.
- Release acceptance was completed on Apple M4 Max and Apple M5 with macOS 27 Beta. Other Apple Silicon generations and older macOS versions were not project-validated, and a minimum macOS version is not yet defined.
- The release is ad-hoc signed and is not Developer ID notarized, so Gatekeeper may require **Open Anyway** on first launch.
- Inference currently invokes the `whisper.cpp` CLI in overlapping audio chunks. Transcription is near-real-time, not zero-latency or latency-guaranteed.
- Release 1.0.0 has no LLM summary, cloud translation sidecar, semantic correction, or structured classroom notes.
- Auto Detect uses automatic language detection, so results depend on the model and audio.
- Clean Transcript applies conservative deduplication and limited high-confidence filtering; it is not a semantic rewrite.
- Feature-branch Clean path verification is designed for this app's single-writer workflow. An uncooperative external process can still mutate the Session immediately after the final check; the app does not provide filesystem locking against other programs.

## For Developers

The formal developer build starts from a clean clone and prepares its locked Python environment and pinned `whisper.cpp` runtime automatically:

```bash
git clone https://github.com/smter6626/live_subtitle_generator.git
cd live_subtitle_generator
./Build\ ClassroomTranscriber.command
```

The build produces `dist/ClassroomTranscriber.app` and runs the packaged runtime verifier before reporting success. The Finder-facing `.command` can also be double-clicked.

After the formal bootstrap has prepared `.venv`, run the source UI with:

```bash
.venv/bin/python ui_app.py
```

Run the unit/contract test suite with:

```bash
.venv/bin/python -m unittest discover -s testCodes -p 'test_*.py' -v
```

Release packaging is documented in [`PACKAGING.md`](PACKAGING.md). The REL1A ZIP entry requires the fixed 1.1.0 identity, the clean expected source commit, this clone's canonical App/provenance/Runtime Manifest, and explicit artifact and retained Human-review extraction paths beneath one task-managed Downloads root:

```bash
mkdir -p "$HOME/Downloads/classroom-transcriber-release/artifacts"
.venv/bin/python scripts/build_release_zip.py \
  --version 1.1.0 \
  --expected-source-commit "$(git rev-parse HEAD)" \
  --task-root "$HOME/Downloads/classroom-transcriber-release" \
  --artifact "$HOME/Downloads/classroom-transcriber-release/artifacts/ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip" \
  --human-review-extraction "$HOME/Downloads/classroom-transcriber-release/human-review"
```

Do not treat this short section as a replacement for the packaging and deployment contracts.

### Current lightweight release workflow

The current Owner-authorized path is [`scripts/release_lightweight.py`](scripts/release_lightweight.py),
not deployment of the legacy protected/signature entry. It uses ordinary local
Reviewer/Human decision references and the existing native Git/gh login:

```bash
.venv/bin/python -B scripts/release_lightweight.py \
  --approval /absolute/Downloads/task/decisions/approval.json status
```

Commands are `status|integrate|prepare|resume|human-gate|publish`. The Reviewer
supplies the local records after actual review; the Executor must not manufacture
Human PASS. `prepare` reuses the original divergent integration and strict gate,
stops for exact final-main review, then on a later call reuses the original fresh
six-checkpoint build and ZIP verifier. It stops again for Human testing of that
exact retained App/ZIP. `publish` requires both PASS and explicit
`publish_allowed: true`; changed bytes, a missing decision, or FAIL stops before
tag/draft/upload. A rebuild requires new Human testing. See the field examples in
[`PACKAGING.md`](PACKAGING.md#current-lightweight-release-workflow).

No root-owned entry, signing key, dedicated group, copied credentials or custom
authentication bridge is required. Prompt-based role separation is the authority;
local hashes fix inputs but do not cryptographically prevent same-uid forgery.
The fixed repository, source/ZIP identities, no-force/no-clobber behavior and
actual remote/download reconciliation remain enforced. Logs/metadata stay local;
terminal output is a short stage or fixed STOP code. This new implementation still
requires independent review and does not claim that a formal 1.1.0 package exists.

The following REL1B/C1/C2 sections describe retained legacy compatibility, not
current deployment requirements. Their root/signature gates are superseded for
the explicit lightweight entry, not silently removed from the old entry.

### REL1B integration controller

REL1A's version/App/ZIP identity foundation and REL1B's integration controller
were independently accepted for their bounded implementation scopes. REL1B
provides `status`, `integrate`, and `resume` through
[`scripts/release_controller.py`](scripts/release_controller.py). The whole Step 1, real main integration, a new App/ZIP,
and publication are pending. Build, package, Human-pass, tag, draft, upload, and
publish are unavailable in this controller.

Production requires an independently controlled approval and a protected entry
under the fixed external trust root. These have **not been deployed**; running
the repository entry fails closed with `TRUST_UNAVAILABLE`. There are no CLI
signer, approval, fixture, or trust-root overrides. The only positional interface
is `release_controller.py status|integrate|resume`. `status` reads local hints
without fetch or repair; a recorded state does not certify completion.

The gate runs the integration clone's original pinned bootstrap and full strict
suite. It stops before executing any preexisting ignored environment and detects
later interpreter, uv, environment-code, or source replacement. A resume cannot
reuse an environment proof from a journal. Preserve stopped evidence for review;
when main already contains the merge but trusted local completion is unavailable,
the result is `MAIN_PRESENT_HUMAN_RECONCILIATION`, without rollback or another push.
Disposable fixture signatures and callback-gate tests authorize only new local
test repositories. See [`PACKAGING.md`](PACKAGING.md#rel1b-approval-integration-and-recovery)
for deployment proposals, transport limits, recovery, and validation commands.

### REL1C1 workflow candidate

The workflow entry accepts `status|build|resume|human-gate|prepare|pipeline-status|pipeline-resume|publish`.
It requires a separately signed workflow approval binding all control modules and the loaded packaging/helper dependency closure,
all required build tools, parent/REL1B/REL1C contracts and final Step 1 decisions.
The legacy REL1B entry keeps its four-module authorization scope. Production trust
and protected entries are still undeployed; repository commands stop without them.
There are no caller-selected trust, receipt, source, signer or fixture options.

`status` reads local recorded hints without accepting decisions or writing anything.
`build` verifies an independently signed exact final-main source receipt, actual Git
objects/parents/tree/bytes and exact remote refs. It persists intent, clones that
source into a new attempt, and calls the original `bootstrap_and_build.sh`. Six
inherited-pipe checkpoints surround Python acquisition, Runtime acquisition/build
and App generation. Each checkpoint rechecks approval/source/tools and previously
acquired executable/import bytes. Only the reviewed stage output paths may appear.
A successful invocation calls the original Runtime verifier, canonical App provenance
validator and ZIP helper, and retains the exact package and Human directory.
No formal build or publication occurred during implementation. C1 was independently
accepted; C2/C3, production deployment, final Step 1 acceptance and actual artifact review
remain pending. `resume` validates surviving artifact facts or retires an unknown
build/package outcome for review without re-execution. An explicitly requested later
`build` uses new paths and preserves earlier attempts; no record restores environment trust.

`human-gate` validates a separate externally signed Owner PASS against the exact
ZIP, source, attempt, App tree/identity and retained extraction. Every artifact
consultation compares actual ZIP member bytes, modes, structure and symlink targets
with that retained App; separately consistent hashes are insufficient. It cannot create or
sign PASS; recorded states and integration permission cannot replace that receipt.
PASS alone enables no publication: a separately signed publication plan and approved
transport are additionally required. New workflow
state and artifacts live separately from REL1B's journal root; attempts preserve
prior ZIPs, Human directories and failed evidence.

For future Human review, use Finder to open the exact retained extraction's
`ClassroomTranscriber.app`, then test model download, microphone/Start/Stop, a second
Session, language choices, Copy New Text, window/scrolling, bilingual Clean controls,
active/stopped rename and full-history Yes/No recovery. Use Privacy & Security →
Open Anyway if macOS blocks this ad-hoc, non-notarized App. Record actual hardware,
language and model limits; historical 1.0.0 App acceptance does not approve 1.1.0.
The receipt protocol and staged-build boundaries are documented in [`PACKAGING.md`](PACKAGING.md#rel1c1-candidate-receipts-and-recovery).

### C2/C3 publication and combined pipeline candidate

The candidate adds a fixed GitHub adapter and routing over the existing
integration/build/Human controllers. It awaits independent review, not real main
integration, App/ZIP acceptance or publication. Production trust and authenticated
transport remain undeployed. The eventual protected-entry interface is:

```text
release_workflow.py prepare
release_workflow.py pipeline-status
release_workflow.py pipeline-resume
release_workflow.py human-gate
release_workflow.py publish
```

`prepare` runs the approved integration controller, then stops for a separately
signed exact-final-main receipt. A later call with that valid receipt runs the
original fresh build/package chain and stops at exact-artifact Human review.
Existing artifacts are validated, not overwritten. `pipeline-status` is strictly
local/read-only and explicitly unverified. No command signs decisions.
`pipeline-resume` resumes only a recorded stage. It cannot start missing work or
automatically rebuild an unknown build; source/Human/remote reconciliation gates
remain independent. The original `resume` keeps its exact C1 behavior.

`publish` rechecks the signed ZIP PASS, source/tools and a signed plan, creates only
the deterministic annotated `1.1.0` tag/fixed draft/one ZIP, verifies downloaded
draft bytes before formal/latest publication, then verifies public metadata and
downloaded bytes again. No force/clobber/history deletion exists. Across invocations,
release/asset ownership requires external signed exact-ID reconciliation; names,
identical fields and checksums are insufficient. Preserve stopped evidence instead
of editing state. Deployment, recovery and receipt details are in
[`PACKAGING.md`](PACKAGING.md#c2c3-publication-pipeline-and-production-gates).

## Architecture

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore

Model Manager
-> integrity-gated model management
```

The ASR path captures microphone audio, creates overlapping chunks, resamples them for Whisper, invokes the local Metal-enabled backend, and writes raw and conservatively cleaned transcript evidence.

## Documentation

- [`README.md`](README.md) — primary English user guide and GitHub landing page
- [`README.zh-CN.md`](README.zh-CN.md) — complete Simplified Chinese user guide
- [`PACKAGING.md`](PACKAGING.md) — developer build, packaging, runtime, and release ZIP contract
- [`docs/deployment_static.md`](docs/deployment_static.md) — stable deployment and platform boundaries
- [`docs/deployment_runtime.md`](docs/deployment_runtime.md) — deployment and release acceptance history
- [`docs/product_polish_static.md`](docs/product_polish_static.md) — stable Product/UX boundaries
- [`docs/product_polish_runtime.md`](docs/product_polish_runtime.md) — Product/UX completion evidence and 1.0.0 release record
- [`docs/repo_map.md`](docs/repo_map.md) — repository ownership, architecture, and change-navigation map

The runtime/history documents are engineering evidence. Ordinary users do not need to read them to install or use the app.
