# macOS Packaging

This project supports a local macOS Apple Silicon development build with PyInstaller.

This is not a release build. It does not include notarization, App Store packaging, Windows packaging, or a universal2 target.

## Install Build Dependency

Use the same Python environment that runs the UI:

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install pyinstaller
```

If you have not installed the UI dependency yet:

```bash
python -m pip install PySide6
```

If the project `venv/` exists but your working PyInstaller/PySide6 install is in another interpreter, run:

```bash
PYTHON=python3 ./scripts/build_macos.sh
```

## Build

From the project root:

```bash
./scripts/build_macos.sh
```

The script:

- respects `PYTHON=/path/to/python` when provided
- uses an active virtualenv, then `venv/bin/python`, then `python3`
- verifies PyInstaller is installed
- removes old `build/` and `dist/`
- runs `pyinstaller packaging/ClassroomTranscriber.spec`
- patches bundled whisper.cpp runtime paths where possible
- applies ad-hoc codesign with `codesign --force --deep --sign -`

Output:

```text
dist/ClassroomTranscriber.app
```

## Debug Build For Crash Triage

If the windowed `.app` exits without a Python traceback, build the console debug target:

```bash
./scripts/build_macos_debug.sh
```

Run the generated executable directly from Terminal:

```bash
./dist/ClassroomTranscriberDebug/ClassroomTranscriberDebug
```

You can also run the release app's internal executable from Terminal:

```bash
./dist/ClassroomTranscriber.app/Contents/MacOS/ClassroomTranscriber
```

This exposes stdout/stderr. If no Python traceback appears but macOS still reports
`EXC_BAD_ACCESS`, the failure is likely in native Qt/PySide cleanup rather than
normal Python exception handling.

The app also writes an early startup and shutdown trace to:

```text
~/Library/Application Support/ClassroomTranscriber/logs/crash_debug.log
```

The log includes frozen status, executable path, cwd, Python version, PySide6/Qt
version, resource paths, main window open, recording start/stop, closeEvent,
`QApplication.aboutToQuit`, `app.exec()` return, and uncaught Python exceptions.

## Clean Build Artifacts

```bash
./scripts/clean_build.sh
```

This deletes:

- `build/`
- `dist/`
- Python `__pycache__` and `.pyc` files outside preserved directories

It does not delete:

- `models/`
- `outputs/`
- `external/whisper.cpp/`
- `venv/`

## Entry Point

The packaged app entry point is:

```text
ui_app.py
```

The source-mode entry remains:

```bash
python ui_app.py
```

## What Is Bundled

The app bundle includes:

```text
ClassroomTranscriber.app/Contents/Resources/bin/whisper-cli
ClassroomTranscriber.app/Contents/Resources/bin/download-ggml-model.sh
ClassroomTranscriber.app/Contents/Resources/bin/libwhisper.1.dylib
ClassroomTranscriber.app/Contents/Resources/bin/libggml*.dylib
```

The app looks for bundled resources through `resource_paths.py`. In a frozen PyInstaller app it checks the `.app` Resources directory; in source mode it uses the project directory.

## What Is Not Bundled

The large model files are not bundled. In particular, `ggml-large-v3.bin` is not included in `ClassroomTranscriber.app`.

Reasons:

- `large-v3` is about 2.9 GB
- it would make every rebuild slow and bulky
- users may prefer `large-v3-turbo`, `medium.en`, or a custom model
- Model Manager already supports selecting, importing, and downloading models

## Writable Data Locations

Source mode keeps the current project-local behavior:

```text
config/settings.json
models/
outputs/
```

Packaged `.app` mode uses user-writable locations:

```text
~/Library/Application Support/ClassroomTranscriber/config/settings.json
~/Documents/ClassroomTranscriber/models/
~/Documents/ClassroomTranscriber/outputs/
```

This avoids writing settings, models, or transcripts inside the `.app` bundle.
`~/Library/Application Support/ClassroomTranscriber/models/` is also scanned for
backward compatibility with earlier development builds.

## Model Manager In Packaged App

The packaged app does not require shell environment variables.

On launch, it should use the bundled `whisper-cli` at:

```text
ClassroomTranscriber.app/Contents/Resources/bin/whisper-cli
```

Models are selected through Model Manager. If no model is selected, Start Recording is disabled and the UI should show:

```text
Cannot start transcription: no model selected.
```

Download Model uses the bundled `download-ggml-model.sh` and downloads into:

```text
~/Documents/ClassroomTranscriber/models/
```

The location can be changed in Model Manager with `Choose Folder`. The selected
download directory is saved in `settings.json` as `download_model_dir`.

## Manual Test

1. Build:

```bash
./scripts/build_macos.sh
```

2. Open:

```bash
open dist/ClassroomTranscriber.app
```

3. Confirm the UI starts.
4. Open `Manage Models`.
5. Select an existing model, import a `.bin` / `.gguf` model, or download one.
6. Click Start Recording.
7. Allow microphone permission if macOS prompts.
8. Confirm Clean/Raw transcript tabs update after the first chunk.
9. Click Stop Recording.
10. Confirm the microphone is released.
11. Check the output folder contains:

```text
raw.txt
clean.txt
session.log
config.json
```

12. Confirm `config.json` records the selected model path.

## Crash Reproduction Matrix

Use the debug build or the release app internal executable above, then check
`crash_debug.log` after each run.

1. Source mode: open -> immediately quit.
2. Packaged app: open -> immediately quit.
3. Packaged app: open Manage Models -> close dialog -> quit.
4. Packaged app: open Manage Models -> select model -> close dialog -> quit.
5. Packaged app: Start -> Stop -> quit.
6. Packaged app: Start -> close the main window directly.
7. Packaged app: open and close twice in a row.

## Gatekeeper Note

This is an ad-hoc signed development app. If macOS blocks it, try right-clicking the app and choosing Open.

If quarantine attributes block local testing, remove them manually:

```bash
xattr -dr com.apple.quarantine dist/ClassroomTranscriber.app
```

## Known Limitations

- Only macOS Apple Silicon is targeted in this packaging flow.
- Windows packaging must be done separately on Windows.
- universal2 is not part of this version.
- Models are managed by Model Manager and are not embedded in the app.
- No notarization.
- No App Store packaging.
- The app still calls `whisper-cli` per chunk; a future server/native binding can reduce process startup overhead.

## Roadmap

- notarization
- universal2 build
- Windows backend and packaging
- whisper.cpp server or native binding
