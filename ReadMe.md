# Classroom Live Transcriber

## 1. Project Goal

This project is a local classroom transcription system for macOS Apple Silicon. The goal is to move from "record first, transcribe later" to a practical live transcript workflow with some delay, stable local processing, and session files that can be reviewed immediately during or after class.

This is not an LLM note-taking system yet. It does not summarize, rewrite, or semantically correct the transcript.

## 2. Current Status

Current main path:

- Desktop UI: `ui_app.py`
- Backend: `whisper.cpp` with Metal on Apple Silicon
- Model: `large-v3`
- Output: per-session `raw.txt`, `clean.txt`, `session.log`, and `config.json`
- Dedup: conservative two-stage boundary dedup
- Legacy CLI and the old `faster-whisper` fallback remain in the codebase for rollback and comparison, but the UI does not expose `turbo` or `faster-whisper`.

The tested production route is:

```text
PySide6 UI -> sounddevice microphone capture -> 48kHz ring buffer
-> 10s chunk / 3s overlap -> 16kHz resample
-> whisper.cpp CLI + Metal + large-v3
-> raw transcript -> simple_dedup -> fuzzy_boundary_dedup -> clean transcript
```

## 3. Architecture

Main UI/runtime files:

- `ui_app.py`: PySide6 desktop UI.
- `settings.py`: fixed paths, beam range, original language mapping, config fields.
- `transcription_controller.py`: start/stop state machine.
- `transcription_engine.py`: audio stream, ring buffer, chunk scheduling, backend calls, dedup pipeline, UI events.
- `transcript_store.py`: session folders and transcript/log/config files.
- `stream_transcribe.py`: legacy CLI entry plus reusable backend/dedup helpers.

State machine:

- `IDLE`
- `STARTING`
- `RECORDING`
- `STOPPING`
- `ERROR`

## 4. Backend: whisper.cpp Metal + large-v3

The UI is fixed to:

```text
Backend: whisper.cpp Metal
Model: large-v3
whisper-cli:
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli

model:
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin
```

The backend writes each 16kHz mono chunk to a temporary PCM16 WAV file, calls `whisper-cli`, parses timestamped output, then removes the temporary file automatically.

The app uses transcription mode only:

- It passes `-l <language_code>`.
- It does not pass `-tr`.
- It does not pass `--translate`.

`backend_migration.md` is retained as historical migration notes from `faster-whisper` to `whisper.cpp`.

## 5. UI Usage

Install PySide6 if needed:

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install PySide6
```

Start the UI:

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python ui_app.py
```

The UI provides:

- Start / Stop recording
- Beam Size selection
- Original Language selection
- Clean transcript tab
- Raw transcript tab
- Logs tab
- Runtime, queue backlog, backend/model/beam/language, and output folder status

Detailed UI operating instructions are in `UI_README.md`.

## 6. Original Language Selection

The UI has an `Original Language` selector. It controls the `whisper-cli -l` parameter directly.

Default:

- `English`

Mappings:

| UI option | whisper-cli parameter |
| --- | --- |
| `English` | `-l en` |
| `Chinese` | `-l zh` |
| `Mixed Chinese/English` | `-l auto` |

This is intended to preserve original-language transcription. It does not enable translation mode.

The app no longer uses `whisper-cli --prompt` for simplified/traditional Chinese control. Chinese uses `-l zh`, mixed Chinese/English uses `-l auto`, and the app still runs `task=transcribe` without `-tr` or `--translate`.

If simplified/traditional normalization is needed later, it should be added as a clean-layer text normalization step, for example with OpenCC, not as a Whisper prompt.

Each session writes these fields to `config.json`:

```json
{
  "original_language_label": "Chinese",
  "whisper_language_code": "zh",
  "task": "transcribe",
  "prompt_used": ""
}
```

`session.log` records the chosen language, prompt status, safe `whisper-cli` command template, per-chunk language/prompt metadata, and parse segment counts.

## 7. Beam Size

Beam Size is selectable from `3` to `8`; default is `5`.

It is passed to `whisper-cli` as:

```bash
-bs <beam_size>
```

Beam Size and Original Language are locked while recording. Stop first, then change them and start a new session.

## 8. Output Files

The UI writes each session under:

```text
outputs/
  YYYY-MM-DD_HH-MM-SS/
    raw.txt
    clean.txt
    session.log
    config.json
```

`raw.txt` contains direct backend output with timestamps.

`clean.txt` contains conservative boundary-deduped output. A small clean-only denylist filters highly recognizable subtitle-template hallucinations such as `中文字幕由 Amara.org 社群提供` and `请订阅我的频道`; `raw.txt` keeps those lines for debugging evidence.

`session.log` records startup config, backend events, chunk submission, transcription events, warnings, errors, and stop completion.

`config.json` records backend/model/beam/language/audio settings, paths, prompt status, and hallucination-filter settings.

## 9. Dedup Pipeline

The dedup layer is intentionally conservative and only targets chunk boundary repetition caused by overlapping audio windows.

Stage 1:

- `simple_dedup()`
- Exact/normalized word-boundary overlap trimming
- Handles common contraction expansion for comparison only

Stage 2:

- `fuzzy_boundary_dedup()`
- Conservative fuzzy boundary trimming
- Compares old tail and new head only
- Uses edit similarity, bigram overlap, content-word overlap, and shared content words

It is not:

- semantic cleanup
- paragraph rewriting
- LLM summarization
- full-text dedup

## 10. Installation

Python environment:

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install PySide6
```

`whisper.cpp` and `large-v3` are expected at:

```text
external/whisper.cpp/build/bin/whisper-cli
external/whisper.cpp/models/ggml-large-v3.bin
```

To verify Metal manually:

```bash
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli \
  -m /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin \
  -f /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/samples/jfk.wav \
  -l en \
  -bs 5
```

Check the startup/system log for Metal/GPU information. Do not use `-ng`, `-tr`, or `--translate` for the live UI path.

## 11. Running the UI

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python ui_app.py
```

Manual validation:

1. Select `Original Language = English`; start; speak English; confirm English transcription.
2. Stop.
3. Select `Original Language = Chinese`; start; speak Chinese; confirm Chinese transcription instead of English translation.
4. Stop.
5. Select `Mixed Chinese/English`; start; speak mixed Chinese and English; confirm the output keeps original languages as much as possible.
6. Check `outputs/<session>/config.json`.
7. Check `outputs/<session>/session.log`.

## 12. Running Tests

UI support tests:

```bash
python testCodes/test_ui_support.py
```

Backend support tests:

```bash
python testCodes/test_backends.py --skip-faster-smoke
```

Dedup regression tests:

```bash
PYTHONPATH=. python testCodes/test_dedup_expanded_cases.py
PYTHONPATH=. python testCodes/test_pseudo_real_boundary_sequences_v3.py
```

Expected coverage includes:

- Original Language mapping: `English -> en`, `Chinese -> zh`, `Mixed Chinese/English -> auto`
- No `-tr` or `--translate` in generated CLI args
- Config language/task/prompt/filter fields
- No `--prompt` in generated CLI args
- Clean-only subtitle-template hallucination filtering
- Final partial chunk duration and low-RMS skip behavior
- Transcript timestamp parsing
- Transcript store append behavior
- Dedup regression behavior

## 13. Legacy CLI Entry

The old CLI entry remains:

```bash
python stream_transcribe.py
```

It is kept for rollback, debugging, and backend comparison. The main user-facing route is now the UI.

Older documentation files are retained but deprecated:

- `ReadMe.md`
- `README_updated.md`
- `backend_migration.md`

Use this `README.md` as the main project documentation.

## 14. Known Limitations

- No LLM cleanup.
- No LLM summary.
- No semantic note structuring.
- No packaged macOS app yet.
- `whisper.cpp` is still called through CLI per chunk; future work may use a persistent server or native binding.
- Clean output is conservative boundary dedup, not semantic correction.
- Mixed Chinese/English uses `-l auto`; final quality must be verified with real classroom audio.

## 15. Roadmap

Near term:

- Stabilize UI during longer classroom sessions.
- Observe queue backlog and stop behavior during 30-90 minute sessions.
- Improve UI ergonomics based on real use.

Later:

- Package as a macOS app after UI stability.
- Consider a long-running whisper.cpp server or native binding to reduce per-chunk process overhead.
- Add optional LLM cleanup and summary as a separate post-processing module, not in the live transcription path.
