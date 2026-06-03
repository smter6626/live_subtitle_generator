# LLM Post-processing Design

This document freezes the first LLM scope for Classroom Live Transcriber and
sets the design boundary for a later DeepSeek API integration.

The current stable product path is local ASR:

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
-> raw.txt / clean.txt / session.log / config.json
```

LLM work must remain outside that live transcription path unless a later design
explicitly reopens this decision.

## Scope and Phases

### Phase 1: after-stop summary

Phase 1 is an after-stop summary pipeline.

- Trigger: only after Stop has completed for a session.
- Input source: `clean.txt` is the first input source and the only required
  transcript input for the first version.
- `raw.txt`: reserved for future optional evidence lookup only. It does not
  participate in Phase 1.
- Output language: default output language is Chinese.
- Output location: write all LLM artifacts under `session_dir/llm/`.
- Required output files:

```text
session_dir/
  raw.txt
  clean.txt
  session.log
  config.json
  llm/
    summary.md
    summary.json
    sections.json
    key_terms.json
    action_items.json
    llm_errors.log
```

Phase 1 does not include minute-based translation, realtime LLM calls, LLM
cleanup of `clean.txt`, or any replacement of existing session files. LLM jobs
must not modify raw.txt or clean.txt.

### Phase 2: minute-based Chinese translation sidecar

Phase 2 is a minute-based Chinese translation sidecar and is a later feature.

- Default state: off.
- Input mode: read-only snapshots of `clean.txt`.
- Output mode: sidecar artifacts only, under a future `session_dir/llm/` or
  similarly isolated translation subdirectory.
- It must not enter audio capture, chunk scheduling, dedup, backend execution,
  or the `TranscriptStore` main write path.
- It must not write back into `raw.txt` or `clean.txt`.
- It is not a Phase 1 acceptance criterion.

The sidecar may poll or receive a safe snapshot signal in a later design, but it
must be implemented as an observer of completed clean transcript text, not as a
participant in ASR production.

## Non-goals

The first version explicitly does not do the following:

- No realtime per-chunk LLM calls.
- No minute-based translation in Phase 1.
- No automatic semantic correction of transcript files.
- No overwrite, append, or rewrite of `raw.txt`, `clean.txt`, `session.log`, or
  `config.json`.
- No LLM work inside microphone capture, ring buffer management, chunk
  scheduling, whisper.cpp backend calls, dedup, or `TranscriptStore` writes.
- No API key storage in repository files, app settings, `config.json`, session
  output, request logs, or response logs.
- No local large language model runtime in the first version.
- No cross-session RAG, cloud sync, or upload of raw audio.
- No automated tests that call a real external LLM API.

## Provider Interface

The LLM implementation should use a provider abstraction so Phase 1 can be
tested with a mock provider and later use DeepSeek without changing parsing,
chunking, prompt, or output code.

Proposed modules for a later implementation:

```text
llm/
  __init__.py
  provider_base.py
  deepseek_provider.py
  transcript_chunker.py
  summary_pipeline.py
  prompt_templates.py
  output_writer.py
  cli.py
```

Minimal provider contract:

```python
class LLMProvider:
    provider_id: str

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str) -> dict:
        """Return parsed JSON or raise a typed provider error."""

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return text/markdown or raise a typed provider error."""
```

Provider errors should be typed enough for the pipeline to distinguish missing
API key, authentication failure, rate limit, timeout, malformed response, and
generic network/API failure. The pipeline catches these errors, writes
`llm_errors.log`, and exits without touching transcript files.

## DeepSeek Settings

Phase 1 provider: DeepSeek API through a small adapter.

API key rule for the first version:

```text
DEEPSEEK_API_KEY
```

The first version reads the DeepSeek API key only from the `DEEPSEEK_API_KEY`
environment variable. It must not read the API key from app settings,
`config/settings.json`, session `config.json`, command-line arguments, checked-in
files, or any session output.

Non-secret DeepSeek defaults should live in the LLM provider module or CLI
defaults, not in the existing `settings.py` app settings path for Phase 1.
Suggested first-version defaults:

- Provider id: `deepseek`.
- Output language: Chinese.
- Temperature: low, for stable summarization.
- Timeout: finite per request.
- Retry: small bounded retry count for transient network/rate-limit failures.
- Request/response logging: disabled in Phase 1.

If request/response logs are introduced later, they must be opt-in, redact all
secrets, and still must not contain the API key.

## Transcript Parsing and Chunking

Phase 1 reads `session_dir/clean.txt` after Stop completes. The current clean
line format is:

```text
[12.34s -> 18.90s] transcript text
```

The parser should reuse the current timestamp convention from `TranscriptStore`
semantics:

- Parse `start`, `end`, and `text` from bracketed timestamp lines.
- Preserve original text exactly in evidence fields.
- Skip empty lines.
- Keep malformed/no-timestamp lines as text-only entries rather than failing the
  entire job.
- Never rewrite the source `clean.txt`.

Chunking should be deterministic and based on timestamp order plus a character
or token budget:

- Prefer contiguous time ranges.
- Keep a small text overlap only inside LLM prompt context if needed.
- Track `chunk_id`, `start_time`, `end_time`, and original line ranges.
- Include session metadata from `config.json` only as read-only context if
  needed; do not write back to `config.json`.
- Use `clean.txt` as the authoritative first source for Phase 1.
- Reserve `raw.txt` as future optional evidence for unclear terms, not as a
  Phase 1 input.

## Prompt Templates

Prompts should live in `llm/prompt_templates.py` in a later implementation,
not inside UI code.

All Phase 1 prompts must enforce:

- Output in Chinese by default.
- Do not invent facts outside the transcript.
- Preserve timestamp grounding.
- Separate explicit transcript evidence from model inference.
- Mark uncertain or likely ASR-error content as unclear instead of silently
  correcting it.
- Suggested ASR corrections are comments only and must not replace transcript
  files.

Section prompt inputs:

```text
session metadata, if available
chunk id
chunk start/end time
clean.txt transcript chunk
```

Section prompt output target:

```json
{
  "chunk_id": "chunk-0001",
  "start_time": 0.0,
  "end_time": 300.0,
  "summary": "Chinese section summary",
  "key_terms": [],
  "action_items": [],
  "unclear_parts": []
}
```

Global prompt inputs:

```text
all section summaries
high-value clean.txt excerpts selected by the chunker/pipeline
```

Global prompt output target:

```markdown
# Summary
## Overview
## Timeline
## Key Terms
## Important Details
## Action Items
## Review Questions
## Unclear / Possible ASR Errors
```

## Output Schema

All output files are written under `session_dir/llm/`. Creating or replacing the
`llm/` directory contents must not modify raw.txt or clean.txt.

`summary.md`:

- Human-readable Chinese summary.
- Includes overview, timeline sections, key terms, action items, review
  questions, and unclear/possible ASR errors.
- Uses timestamp references wherever possible.

`summary.json`:

```json
{
  "schema_version": 1,
  "provider": "deepseek",
  "output_language": "zh",
  "source": {
    "session_dir": "...",
    "transcript": "clean.txt",
    "raw_used": false
  },
  "generated_at": "ISO-8601 timestamp",
  "overview": "...",
  "timeline": [],
  "review_questions": [],
  "unclear_parts": []
}
```

`sections.json`:

```json
{
  "schema_version": 1,
  "sections": [
    {
      "section_id": "section-0001",
      "start_time": 0.0,
      "end_time": 300.0,
      "title": "...",
      "summary": "...",
      "evidence": ["00:00-05:00"]
    }
  ]
}
```

`key_terms.json`:

```json
{
  "schema_version": 1,
  "key_terms": [
    {
      "term": "...",
      "meaning": "...",
      "evidence": "00:00-05:00",
      "confidence": "low|medium|high"
    }
  ]
}
```

`action_items.json`:

```json
{
  "schema_version": 1,
  "action_items": [
    {
      "time": "00:42:15",
      "item": "...",
      "owner": null,
      "due": null,
      "evidence": "..."
    }
  ]
}
```

`llm_errors.log`:

- Created if an LLM run fails or has recoverable warnings.
- Contains timestamps, sanitized provider error category, and safe diagnostic
  text.
- Must not contain the API key, authorization headers, full raw request bodies,
  or full raw response bodies.

## Privacy and API Key Handling

The UI and CLI must communicate clearly that DeepSeek post-processing sends
transcript text to an external API. Users must be able to leave LLM disabled and
continue using local ASR normally.

Hard rules:

- Read DeepSeek API key only from `DEEPSEEK_API_KEY` in Phase 1.
- Do not save API key to the repository.
- Do not save API key to app settings.
- Do not save API key to `config.json`.
- Do not save API key to `summary.md`, JSON outputs, `llm_errors.log`, request
  logs, response logs, or any other session output.
- Do not print API key in terminal output.
- Do not include API key in exception messages.
- Do not add API key fields to UI settings in Phase 1.

Transcript privacy:

- `clean.txt` content is sent to the provider in Phase 1.
- `raw.txt` and audio files are not sent in Phase 1.
- Future raw evidence support must be opt-in at design level and must still not
  modify source transcript files.

## Error Handling

LLM failure isolation is mandatory.

All LLM failures must not affect:

- `raw.txt`
- `clean.txt`
- `session.log`
- `config.json`
- Start/Stop behavior
- microphone release
- UI main thread stability
- future recordings

Expected failure cases:

- Missing `DEEPSEEK_API_KEY`.
- Invalid API key.
- Network unavailable.
- Provider timeout.
- Rate limit.
- Malformed or non-JSON model response.
- Partial section failure during map-reduce.
- User cancellation in a later UI phase.

Handling rules:

- Write sanitized failure details to `session_dir/llm/llm_errors.log`.
- Return a non-zero CLI exit code for failed CLI runs.
- Do not delete or truncate existing transcript files.
- Use atomic writes for final JSON/Markdown outputs where practical: write to a
  temporary file under `llm/`, then rename.
- If partial files exist from a failed run, leave them clearly marked or replace
  only files inside `llm/`.
- Never propagate LLM exceptions into the audio capture or transcription worker
  threads.

## CLI Workflow

Phase 1 implementation order starts with CLI.

Proposed CLI shape:

```bash
python -m llm.cli summarize outputs/YYYY-MM-DD_HH-MM-SS
```

Workflow:

1. Validate `session_dir` exists.
2. Validate `session_dir/clean.txt` exists and is readable.
3. Validate `DEEPSEEK_API_KEY` exists in the environment.
4. Create `session_dir/llm/`.
5. Parse and chunk `clean.txt`.
6. Run mock provider or DeepSeek provider depending on CLI mode.
7. Write `summary.md`, `summary.json`, `sections.json`, `key_terms.json`,
   `action_items.json`.
8. Write `llm_errors.log` on failure or warnings.
9. Exit without modifying `raw.txt`, `clean.txt`, `session.log`, or
   `config.json`.

Implementation sequence:

1. CLI first.
2. Mock tests second.
3. Real API manual test third.
4. UI integration last.

The CLI must be usable against an existing completed session, independent of the
desktop UI.

## UI Workflow

UI integration is last and must remain minimal.

Future UI behavior:

- Enable `Generate Summary` only after Stop has completed and a current session
  directory exists.
- Run LLM work on a background thread or worker, never on the Qt main thread.
- Show status: idle, running, failed, complete.
- Provide `Open Summary` only when `summary.md` exists.
- Display an explicit privacy notice before sending transcript text to DeepSeek.
- Keep LLM disabled when `DEEPSEEK_API_KEY` is missing.

The UI must not call LLM during recording by default. It must not connect LLM
work to audio capture, chunk scheduling, dedup, whisper.cpp backend execution,
or `TranscriptStore` append operations.

Phase 2 translation, when designed later, should appear as an optional sidecar
toggle and remain off by default.

## Tests

Automated tests use a mock provider only. They must not call the real DeepSeek
API and must not require `DEEPSEEK_API_KEY`.

Suggested later test files:

```text
testCodes/test_llm_chunker.py
testCodes/test_llm_pipeline.py
testCodes/test_llm_outputs.py
testCodes/test_llm_provider_mock.py
```

Required coverage for the later implementation:

- `clean.txt` timestamp parser.
- No-timestamp fallback lines.
- Empty transcript handling.
- Deterministic chunking.
- Prompt payload construction.
- Mock provider success path.
- Mock provider malformed response path.
- Missing `DEEPSEEK_API_KEY` CLI behavior.
- Output schema validation.
- API key redaction from all outputs/logs.
- LLM error does not modify `raw.txt` or `clean.txt`.
- Phase 1 does not create minute-based translation outputs.

Manual real API test, after mock tests pass:

- Use a disposable completed session.
- Set `DEEPSEEK_API_KEY` in the shell environment only.
- Run the CLI manually.
- Inspect `session_dir/llm/` output quality.
- Confirm no API key appears in repo diff, settings, `config.json`, session
  output, terminal transcript, or logs.

## Risks and Rollback

Primary risks:

- Accidentally moving LLM into the realtime ASR path.
- Treating minute-based translation as Phase 1 work.
- Saving API keys into settings or session files.
- Rewriting `clean.txt` as an LLM-corrected transcript.
- Blocking Stop or UI shutdown on network/API work.
- Over-trusting LLM output without timestamp grounding.

Rollback strategy:

- Because Phase 1 outputs are isolated under `session_dir/llm/`, rollback should
  be deleting or ignoring that directory.
- CLI code can be disabled without changing ASR behavior.
- UI integration, once added later, should be feature-gated and removable
  without touching `TranscriptionEngine` or `TranscriptStore` main writes.
- If implementation ever modifies files outside the planned LLM modules or UI
  button/status integration, stop and inspect the diff before continuing.

## Minimal Production Code Change Plan

This current task creates only this design document. No production code changes
are part of this step.

Later Phase 1 implementation should be minimal and ordered:

1. Add isolated `llm/` modules and a CLI entry point.
2. Add mock-provider tests for parser, chunker, pipeline, outputs, and error
   isolation.
3. Run one real DeepSeek API manual test from the shell with
   `DEEPSEEK_API_KEY`.
4. Add UI integration last, limited to a Generate Summary action, status display,
   privacy notice, and opening `summary.md`.

Files that should stay out of the initial CLI implementation unless a later UI
task explicitly requires them:

```text
ui_app.py
transcription_engine.py
transcription_controller.py
transcript_store.py
stream_transcribe.py
settings.py
model_manager.py
resource_paths.py
```

If UI integration later touches `ui_app.py`, the change should be an isolated
button/status/background-job wrapper around the already-tested CLI/pipeline. It
must not alter Start/Stop semantics, microphone lifecycle, raw/clean writes,
dedup behavior, backend command construction, model management, or resource path
resolution.
