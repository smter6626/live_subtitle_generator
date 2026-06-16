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

The LLM branch is split into four explicit phases. Older notes that said
"Phase 1 summary" now mean **Phase 1A**. Older notes that said "Phase 2
minute-based translation" now mean **Phase 2A dynamic Chinese readable sidecar**
plus **Phase 2B in-app preview**.

### Evidence Layer Is Immutable

The existing session evidence layer is:

```text
raw.txt
clean.txt
session.log
config.json
```

LLM features must never modify, overwrite, delete, rename, truncate, append LLM
content to, translate into, correct into, or mix generated output into these
files. They are the stable ASR evidence layer.

### LLM Is Sidecar Only

```text
Existing realtime path:
local ASR + raw / clean output

New LLM features:
optional, asynchronous, sidecar reads, derived outputs
```

LLM work must not enter `audio capture`, `ring buffer`, `chunk scheduling`,
`resample`, `WhisperCppBackend`, the `TranscriptionEngine` transcription worker
loop, `simple_dedup()`, `fuzzy_boundary_dedup()`, `TranscriptStore` raw/clean
main writes, Start/Stop, microphone release, or the UI main thread.

### Phase 1A: after-stop Chinese summary

Phase 1A is the current first-priority feature.

- Trigger: only after Stop has completed and the Whisper queue has drained.
- Required input: complete `session_dir/clean.txt`.
- Optional input: read-only session metadata.
- Not required in first version: `raw.txt`, audio, cross-session history, or an
  external knowledge base.
- `raw.txt`: future optional evidence only; it does not participate in Phase 1A.
- Output language: Chinese by default.
- Output location: `session_dir/llm/`.
- Pipeline:

```text
read complete clean.txt
-> transcript parser
-> chunker
-> map-reduce summary pipeline
-> Chinese structured summary
-> write session_dir/llm/
```

Required Phase 1A outputs:

```text
session_dir/llm/
  summary.md
  summary.json
  sections.json
  key_terms.json
  action_items.json
  llm_errors.log
```

The summary should include course overview, timeline-based sections, stage 1 /
stage 2 / stage 3 style organization where useful, key concepts, important
details, terms and explanations, assignments, deadlines, project instructions,
professor-emphasized points, action items, review questions, unclear parts,
possible ASR errors, and timestamp grounding.

### Phase 1B: after-stop Chinese readable transcript

Phase 1B adds a derived product that is different from summary:

```text
a complete Chinese readable transcript for human review
```

It is not evidence and it is not a summary. It reads the completed `clean.txt`
after Stop and writes derived state/views only under `session_dir/llm/`.

Pipeline:

```text
Stop complete
-> read complete clean.txt
-> LLM structured filtering, translation, and conservative revision
-> state JSON
-> local renderer
-> Markdown
-> HTML
```

Planned Phase 1B outputs:

```text
session_dir/llm/
  readable_zh_final_state.json
  readable_zh_final.md
  readable_zh_final.html
  review_zh_final.md
  review_zh_final.html
  readable_zh_errors.log
```

There are two views:

- Reading view: clean, coherent, suitable for after-class reading, allowed to
  omit obvious repetition, preserves important uncertainty and timestamp
  grounding.
- Review view: keeps suspected duplicates, revision traces, uncertain terms,
  possible corrections, and enough structure to compare with `clean.txt`.

Markdown and HTML are derived views. The real state source is:

```text
state JSON
```

Renderer path:

```text
LLM structured output
-> schema validation
-> state JSON
-> local renderer
-> Markdown
-> HTML
```

The LLM must not directly free-generate and overwrite the entire Markdown file.

### Phase 2A: dynamic Chinese readable sidecar

Phase 2A is the optional dynamic sidecar run during recording. It is the rolling
version of Phase 1B, not part of realtime ASR.

- Default state: off.
- Derived live outputs:

```text
session_dir/llm/
  live_readable_zh_state.json
  live_readable_zh_revisions.jsonl
  live_readable_zh.md
  live_readable_zh.html
  live_review_zh.md
  live_review_zh.html
  live_readable_zh_errors.log
```

Initial scheduling parameters are configurable starting values, not permanent
constants:

```text
interval_seconds = 30
clean_context_window_seconds = 40
editable_window_seconds = 60
```

Each LLM request should include newline-complete snapshot context:

```text
A. recent clean.txt timestamped snapshot, about 40 seconds
B. current Chinese readable editable structured segments, about 60 seconds
C. short glossary snapshot
D. current state revision
E. frozen boundary time
```

LLM output should be a structured JSON patch, not full Markdown. Allowed patch
operations are:

```text
append
replace
annotate
mark_duplicate
freeze
```

The local validator must reject attempts to modify frozen segments, edit
evidence files, overwrite history, use unknown operations, mismatch
`base_revision`, move timestamps backward, duplicate `segment_id`, cross the
editable window, or return invalid JSON/schema.

Only one API request may be in flight. If another trigger fires while a request
is running, the sidecar should use pending snapshot coalescing: keep only the
latest pending snapshot and drop stale ones. Prefer missing an update over
creating backlog.

### Phase 2B: in-app Markdown / HTML preview

Phase 2B integrates the readable sidecar into the PySide6 UI after Phase 2A is
stable. The product should not depend on Typora, an external browser, or
`QWebEngineView`.

Recommended UI renderer:

```text
state JSON
-> local renderer
-> HTML
-> QTextBrowser.setHtml()
```

Markdown files remain for archive/export. Typora and browsers are development
spot-check tools only.

Minimal future UI:

```text
LLM Chinese readable tab
reading / review mode toggle
sidecar switch
provider status
Idle / Running / Failed / Complete
last updated time
Open Markdown
Open HTML
```

Background workers must signal preview updates. The Qt main thread reads the
latest safe HTML and calls `QTextBrowser.setHtml()`. Sidecar workers must never
operate Qt widgets directly.

## Non-goals

The current documentation update and later Phase 1A/1B work explicitly do not do
the following:

- No production code changes in this documentation step.
- No provider, renderer, CLI, sidecar, UI, or test implementation in this step.
- No realtime per-chunk LLM calls in Phase 1A or Phase 1B.
- No dynamic sidecar until Phase 2A.
- No UI integration until Phase 2B.
- No automatic correction that overwrites `clean.txt`.
- No overwrite, append, delete, rename, truncate, translation replacement,
  correction replacement, or LLM content mixing for `raw.txt`, `clean.txt`,
  `session.log`, or `config.json`.
- No LLM work inside microphone capture, ring buffer management, chunk
  scheduling, resample, whisper.cpp backend calls, dedup, `TranscriptStore`
  main writes, Start/Stop, microphone release, or the UI main thread.
- No API key storage in repository files, `/docs`, app settings,
  `config/settings.json`, session `config.json`, transcript files, request logs,
  response logs, Markdown, HTML, JSON state, or error logs.
- No local large language model runtime in the first version.
- No cross-session RAG, session browser, persistent whisper backend, cloud sync,
  or upload of raw audio in this branch.
- No automated tests that call a real external LLM API.

## Provider Interface

The LLM implementation should use a provider abstraction so Phase 1A, Phase 1B,
Phase 2A, and Phase 2B can be tested with a mock provider and later use
DeepSeek / OpenAI-compatible APIs without changing parsing, chunking, prompt,
state, renderer, or output code.

Proposed modules for a later implementation:

```text
llm/
  __init__.py
  provider_base.py
  deepseek_provider.py
  openai_compatible_provider.py
  transcript_chunker.py
  summary_pipeline.py
  prompt_templates.py
  state_schema.py
  output_writer.py
  renderer.py
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

Phase 1A/1B provider: DeepSeek / OpenAI-compatible API through a small adapter.

API key rule for the first version:

```text
DEEPSEEK_API_KEY
```

The first version reads the DeepSeek API key only from the `DEEPSEEK_API_KEY`
environment variable. It must not read the API key from app settings,
`config/settings.json`, session `config.json`, command-line arguments, checked-in
files, `/docs`, or any session output.

Non-secret DeepSeek defaults should live in the LLM provider module or CLI
defaults, not in the existing `settings.py` app settings path for Phase 1A/1B.
The model name and endpoint must not be hardcoded as permanent constants; reserve
environment variables or provider settings for them. Suggested first-version
defaults:

- Provider id: `deepseek`.
- Output language: Chinese.
- Model name: configurable, for example through `DEEPSEEK_MODEL` or provider
  settings.
- Endpoint: configurable provider setting.
- Temperature: low, for stable summarization.
- Timeout: finite per request.
- Retry: small bounded retry count for transient network/rate-limit failures.
- Request/response logging: disabled in Phase 1A/1B.

If request/response logs are introduced later, they must be opt-in, redact all
secrets, and still must not contain the API key.

## Transcript Parsing and Chunking

Phase 1A and Phase 1B read `session_dir/clean.txt` after Stop completes. The current clean
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
- Include session metadata only as read-only context if needed; do not write
  back to `config.json`.
- Use `clean.txt` as the authoritative first source for Phase 1A/1B.
- Reserve `raw.txt` as future optional evidence for unclear terms, not as a
  Phase 1A input.

## Prompt Templates

Prompts should live in `llm/prompt_templates.py` in a later implementation,
not inside UI code.

All Phase 1A/1B and Phase 2A prompts must enforce:

- Output in Chinese by default.
- Do not invent facts outside the transcript.
- Preserve timestamp grounding.
- Separate explicit transcript evidence from model inference.
- Mark uncertain or likely ASR-error content as unclear instead of silently
  correcting it.
- Suggested ASR corrections are comments only and must not replace transcript
  files.
- Do not let the model directly overwrite full Markdown/HTML views.
- For readable transcript phases, ask for structured JSON/state or JSON patch
  only, then render locally.

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
`llm/` directory contents must not modify `raw.txt`, `clean.txt`, `session.log`,
or `config.json`.

### Phase 1A Summary Outputs

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

### Phase 1B Readable Transcript Outputs

`readable_zh_final_state.json` is the authoritative state source for the final
Chinese readable transcript. Markdown and HTML are rendered from this state.

Planned files:

```text
readable_zh_final_state.json
readable_zh_final.md
readable_zh_final.html
review_zh_final.md
review_zh_final.html
readable_zh_errors.log
```

Suggested state shape:

```json
{
  "schema_version": 1,
  "revision": 1,
  "source": {
    "transcript": "clean.txt",
    "raw_used": false
  },
  "segments": [
    {
      "segment_id": "seg_0001",
      "start": 0.0,
      "end": 12.4,
      "source_text": "...",
      "text_zh": "...",
      "annotations": [],
      "evidence": ["00:00-00:12"],
      "status": "editable|frozen"
    }
  ]
}
```

Markdown annotation semantics:

```markdown
~~deleted text~~
```

Means suspected semantic repetition, oral restart, or a fragment covered by a
later complete expression.

```markdown
*italic text*
```

Means professional term, proper noun, uncertain translation, or a term that
should keep its English form.

```markdown
**[可疑] text**
```

Means logically incomplete, possible ASR error, or needs human review.

```html
<u><strong>[高风险可疑] text</strong></u>
```

Means high-value but unreliable information such as deadlines, exam
requirements, assignment requirements, grading rules, project submission
requirements, or similar course-critical content.

Standard Markdown has no native underline; use controlled HTML tags for this
high-risk underline. Do not misuse `_text_` for underline.

### Phase 2A Live Sidecar Outputs

Planned files:

```text
live_readable_zh_state.json
live_readable_zh_revisions.jsonl
live_readable_zh.md
live_readable_zh.html
live_review_zh.md
live_review_zh.html
live_readable_zh_errors.log
```

`live_readable_zh_state.json` stores the current structured segments.
`live_readable_zh_revisions.jsonl` stores append-only revision history for audit
and rollback. Markdown and HTML are derived views.

## Privacy and API Key Handling

The UI and CLI must communicate clearly that DeepSeek post-processing sends
transcript text to an external API. Users must be able to leave LLM disabled and
continue using local ASR normally.

Hard rules:

- Read DeepSeek API key only from `DEEPSEEK_API_KEY` in Phase 1A/1B.
- Do not save API key to the repository.
- Do not save API key to `/docs`.
- Do not save API key to app settings.
- Do not save API key to `config/settings.json`.
- Do not save API key to `config.json`.
- Do not save API key to `raw.txt`, `clean.txt`, `summary.md`, Markdown outputs,
  HTML outputs, JSON state, `llm_errors.log`, request logs, response logs, or
  any other session output.
- Do not print API key in terminal output.
- Do not include API key in exception messages.
- Do not add API key fields to UI settings in Phase 1A/1B.

Transcript privacy:

- `clean.txt` content is sent to the provider in Phase 1A/1B.
- `raw.txt` and audio files are not sent in Phase 1A/1B.
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
- HTTP error.
- Provider error.
- Rate limit.
- Malformed or non-JSON model response.
- Schema validation failure.
- Renderer failure.
- Sidecar backlog.
- Partial section failure during map-reduce.
- User cancellation in a later UI phase.
- Application close.

Handling rules:

- Write sanitized failure details to `session_dir/llm/llm_errors.log`.
- Return a non-zero CLI exit code for failed CLI runs.
- Do not delete or truncate existing transcript files.
- Preserve `raw.txt`, `clean.txt`, `session.log`, and `config.json`.
- Preserve the latest valid LLM derived output when a later run fails.
- Use atomic writes for final JSON/Markdown outputs where practical: write to a
  temporary file under `llm/`, then rename.
- Dynamic sidecar files must use atomic replace: write temp file, flush, fsync
  where appropriate, then `os.replace()`.
- If partial files exist from a failed run, leave them clearly marked or replace
  only files inside `llm/`.
- Never propagate LLM exceptions into the audio capture or transcription worker
  threads.
- Do not block Stop drain.
- Do not affect microphone release or the next Start.

## CLI Workflow

Phase 1A/1B implementation starts with CLI and mock provider before real API or
UI work.

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
7. For Phase 1A, write `summary.md`, `summary.json`, `sections.json`, `key_terms.json`,
   `action_items.json`.
8. For Phase 1B, write `readable_zh_final_state.json`, `readable_zh_final.md`,
   `readable_zh_final.html`, `review_zh_final.md`, and `review_zh_final.html`.
9. Write LLM-specific error logs on failure or warnings.
10. Exit without modifying `raw.txt`, `clean.txt`, `session.log`, or
   `config.json`.

Implementation sequence:

1. CLI first.
2. Mock provider second.
3. Mock tests and structured outputs third.
4. Error isolation and secret leakage tests next.
5. Real API manual smoke test after mocks pass.
6. UI integration last.

The CLI must be usable against an existing completed session, independent of the
desktop UI.

## UI Workflow

UI integration is last and must remain minimal.

Phase 1A/1B future UI behavior:

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

Phase 2B future UI behavior:

- Add an LLM Chinese readable tab.
- Offer reading/review mode toggle.
- Add sidecar switch, provider status, last update time, Open Markdown, and Open
  HTML actions.
- Render through `QTextBrowser.setHtml()` from locally rendered HTML.
- Do not depend on Typora, external browsers, or `QWebEngineView`.
- Typora and browsers are development spot-check tools only.
- Sidecar worker emits a preview update signal; Qt main thread reads safe HTML
  and calls `QTextBrowser.setHtml()`.
- Preserve scroll position where practical; if the user is at the bottom,
  auto-scroll to bottom after refresh.

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
- Chunk overlap.
- Prompt payload construction.
- Mock provider success path.
- Mock provider malformed response path.
- Mock provider failure and error injection.
- Missing `DEEPSEEK_API_KEY` CLI behavior.
- Output schema validation.
- API key redaction from all outputs/logs.
- Summary Markdown/JSON, sections, key terms, and action items outputs.
- Readable final state, Markdown, HTML, review Markdown, and review HTML outputs.
- HTML escaping.
- Annotation rendering.
- `raw.txt`, `clean.txt`, `session.log`, and `config.json` unchanged.
- Phase 1A/1B do not create dynamic live outputs.

Phase 2A test coverage should include:

- Newline-complete snapshot.
- High-water mark.
- Configurable `interval_seconds = 30`.
- `clean_context_window_seconds = 40`.
- `editable_window_seconds = 60`.
- Frozen segment cannot be rewritten.
- Editable segment can be replaced.
- `mark_duplicate` does not delete evidence.
- Annotation rendering.
- Monotonic revision numbers.
- `base_revision` mismatch rejected.
- Unknown operation rejected.
- Invalid schema rejected.
- At most one in-flight request.
- Pending snapshot coalescing.
- No sidecar backlog.
- API timeout preserves latest valid output.
- Renderer failure preserves latest valid output.
- Atomic replace.
- Stop final reconciliation.
- Sidecar disabled/off leaves ASR independently usable.
- LLM errors do not affect Start/Stop, microphone release, raw/clean files, or
  the UI main thread.

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
- Treating Phase 2A dynamic sidecar as Phase 1A/1B work.
- Saving API keys into settings or session files.
- Rewriting `clean.txt` as an LLM-corrected transcript.
- Treating Markdown as the real state source instead of state JSON.
- Letting LLM directly overwrite whole Markdown/HTML files.
- Blocking Stop or UI shutdown on network/API work.
- Creating sidecar backlog instead of coalescing pending snapshots.
- Hardcoding DeepSeek model name or endpoint.
- Treating Typora, external browsers, or `QWebEngineView` as product
  dependencies.
- Over-trusting LLM output without timestamp grounding.

Rollback strategy:

- Because LLM outputs are isolated under `session_dir/llm/`, rollback should
  be deleting or ignoring that directory.
- CLI code can be disabled without changing ASR behavior.
- UI integration, once added later, should be feature-gated and removable
  without touching `TranscriptionEngine` or `TranscriptStore` main writes.
- If Phase 2A is unstable, disable the sidecar and keep Phase 1A/1B after-stop
  outputs.
- If implementation ever modifies files outside the planned LLM modules or UI
  button/status integration, stop and inspect the diff before continuing.

## Minimal Production Code Change Plan

This current task updates design documents only. No production code changes,
provider implementation, renderer implementation, CLI implementation, sidecar
implementation, UI implementation, or test code are part of this step.

Current checkpoint as of 2026-06-03: Step 1, Step 2, and Step 3 are complete.
The isolated `llm/` package skeleton exists only as importable boundaries.
Parser / chunker business logic, mock provider, real HTTP API, summary pipeline,
output writer, renderer, CLI, UI, and Phase 2A sidecar are not implemented yet.
Resume development at Step 4: implement transcript parser / chunker.

Later implementation order:

```text
Step 1: freeze requirements and architecture boundaries
Step 2: update design documents
Step 3: create isolated llm/ module skeleton
Step 4: implement transcript parser / chunker
Step 5: implement provider interface and mock provider
Step 6: implement output writer, state schema, renderer
Step 7: implement Phase 1A after-stop summary mock pipeline
Step 8: implement Phase 1B after-stop readable transcript mock pipeline
Step 9: add CLI entry point and run with mock
Step 10: add mock tests, error injection, secret leakage tests
Step 11: implement DeepSeek / OpenAI-compatible provider
Step 12: local manual real API smoke test
Step 13: validate Phase 1A / 1B real classroom session output quality
Step 14: implement Phase 2A rolling sidecar
Step 15: validate single worker, coalescing, atomic replace, final reconciliation
Step 16: implement Phase 2B in-app QTextBrowser preview
Step 17: long classroom stability test
Step 18: decide default switch strategy only after stability is proven
```

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
