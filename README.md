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
- Separate Original Language selection for English, Chinese, Japanese, French, Spanish, German, Korean, or Auto Detect audio
- Beam control from 3 to 8, with a default of 5
- Persistent model, Beam, interface language, model location, and output settings
- Timestamped session evidence files
- A custom macOS app icon in the packaged release

## Download

The current formal release is **1.0.0**:

- [Classroom Transcriber 1.0.0 GitHub Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0)
- Release asset: `ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip`

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
14. Click **Open Output Folder** to find the session files.

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
├── clean.txt
├── session.log
└── config.json
```

- `raw.txt` — original timestamped transcript evidence from the backend
- `clean.txt` — a more readable transcript after conservative boundary deduplication and limited filtering
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

## Known Limitations

- The downloadable 1.0.0 artifact is macOS Apple Silicon only. There is no Intel Mac or Windows release.
- Release acceptance was completed on Apple M4 Max and Apple M5 with macOS 27 Beta. Other Apple Silicon generations and older macOS versions were not project-validated, and a minimum macOS version is not yet defined.
- The release is ad-hoc signed and is not Developer ID notarized, so Gatekeeper may require **Open Anyway** on first launch.
- Inference currently invokes the `whisper.cpp` CLI in overlapping audio chunks. Transcription is near-real-time, not zero-latency or latency-guaranteed.
- Release 1.0.0 has no LLM summary, cloud translation sidecar, semantic correction, or structured classroom notes.
- Auto Detect uses automatic language detection, so results depend on the model and audio.
- Clean Transcript applies conservative deduplication and limited high-confidence filtering; it is not a semantic rewrite.

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

Release packaging is documented in [`PACKAGING.md`](PACKAGING.md). In brief, a clean formal build is followed by:

```bash
.venv/bin/python scripts/build_release_zip.py --version <version>
```

Do not treat this short section as a replacement for the packaging and deployment contracts.

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
