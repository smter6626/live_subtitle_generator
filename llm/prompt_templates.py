from dataclasses import dataclass, field
from typing import Any

from llm.transcript_chunker import TranscriptChunk


PHASE1A_SYSTEM_PROMPT = """You are a conservative transcript post-processor.
Output language: Chinese.
Use only the provided clean transcript text.
Do not hallucinate or add information outside the transcript.
Keep timestamp grounding for claims whenever possible.
Separate explicit transcript evidence from inference.
Mark uncertain content as unclear.
ASR corrections must appear only as possible correction suggestions.
Do not modify, overwrite, or replace clean.txt.
Return structured JSON matching the requested schema."""


PHASE1B_SYSTEM_PROMPT = """You are a conservative readable transcript post-processor.
Output language: Chinese.
Produce a Chinese readable transcript from clean transcript evidence only.
Do not hallucinate or add information outside the transcript.
Keep timestamp grounding for each segment whenever possible.
Return structured JSON state; state JSON is the true source.
Markdown and HTML must be derived later by the local renderer.
Mark uncertain content as unclear or suspicious.
ASR corrections must appear only as possible correction annotations.
Do not modify, overwrite, or replace clean.txt.
Do not directly generate full Markdown or HTML."""


@dataclass(frozen=True)
class PromptPayload:
    """Prompt payload plus metadata used for deterministic tests and providers."""

    system_prompt: str
    user_prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)


def build_section_summary_payload(
    *,
    chunk: TranscriptChunk,
    output_language: str = "zh",
    session_metadata: dict[str, Any] | None = None,
) -> PromptPayload:
    """Build a Phase 1A section-summary prompt payload for one transcript chunk."""

    metadata = {
        "phase": "Phase 1A",
        "task": "section_summary",
        "output_language": output_language,
        "chunk_id": chunk.chunk_id,
        "chunk_start": chunk.start,
        "chunk_end": chunk.end,
        "source_lines": list(chunk.source_lines),
        "session_metadata": session_metadata or {},
    }
    source_lines = ", ".join(str(line) for line in chunk.source_lines) or "none"
    user_prompt = f"""Task: produce one Chinese section summary as structured JSON.
Schema fields may include: title, summary, key_terms, action_items, review_questions, unclear_parts.
Required constraints:
- Chinese output.
- timestamp grounding.
- no hallucination.
- use only clean transcript evidence.
- mark unclear content as unclear.
- possible correction only for ASR uncertainty.
- do not overwrite clean.txt.

Chunk id: {chunk.chunk_id}
Chunk time range: {chunk.start} -> {chunk.end}
Source line indexes: {source_lines}
Clean transcript chunk:
{chunk.text}
"""
    return PromptPayload(
        system_prompt=PHASE1A_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        metadata=metadata,
    )


def build_section_summary_prompt(*, chunk_id: str, transcript_text: str) -> tuple[str, str]:
    """Return system/user prompts for a Phase 1A section summary."""

    user_prompt = f"""Task: produce one Chinese section summary as structured JSON.
Required constraints:
- Chinese output.
- timestamp grounding.
- no hallucination.
- mark unclear content as unclear.
- possible correction only for ASR uncertainty.
- do not overwrite clean.txt.

Chunk id: {chunk_id}
Clean transcript chunk:
{transcript_text}
"""
    return PHASE1A_SYSTEM_PROMPT, user_prompt


def build_global_summary_payload(
    *,
    section_summaries: str,
    output_language: str = "zh",
    session_metadata: dict[str, Any] | None = None,
) -> PromptPayload:
    """Build a Phase 1A global-summary prompt payload from section summaries."""

    metadata = {
        "phase": "Phase 1A",
        "task": "global_summary",
        "output_language": output_language,
        "session_metadata": session_metadata or {},
    }
    user_prompt = f"""Task: produce the final Chinese classroom summary as structured JSON.
Schema fields may include: overview, key_terms, action_items, review_questions, unclear_parts.
Required constraints:
- Chinese output.
- preserve timestamp grounding from section summaries.
- no hallucination or outside knowledge.
- distinguish transcript evidence from inference.
- mark uncertain content as unclear.
- possible correction only for ASR uncertainty.
- do not overwrite clean.txt.

Section summaries:
{section_summaries}
"""
    return PromptPayload(
        system_prompt=PHASE1A_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        metadata=metadata,
    )


def build_global_summary_prompt(*, section_summaries: str) -> tuple[str, str]:
    """Return system/user prompts for a Phase 1A global summary."""

    payload = build_global_summary_payload(section_summaries=section_summaries)
    return payload.system_prompt, payload.user_prompt


def build_readable_transcript_prompt(*, transcript_text: str) -> tuple[str, str]:
    """Return prompts for Phase 1B readable transcript structured output."""

    user_prompt = f"""Task: produce Chinese readable transcript segments as structured JSON.
Required constraints:
- Chinese readable transcript.
- use only clean transcript evidence.
- no hallucination.
- timestamp grounding.
- structured JSON/state output.
- state JSON is the true source.
- Markdown / HTML are derived by the local renderer.
- mark uncertain content as unclear or suspicious.
- possible correction only for ASR uncertainty.
- do not overwrite clean.txt.
- do not directly generate full Markdown or HTML.

Clean transcript chunk:
{transcript_text}
"""
    return PHASE1B_SYSTEM_PROMPT, user_prompt


def build_readable_transcript_payload(
    *,
    chunk: TranscriptChunk,
    output_language: str = "zh",
    session_metadata: dict[str, Any] | None = None,
) -> PromptPayload:
    """Build a Phase 1B readable-transcript prompt payload for one chunk."""

    metadata = {
        "phase": "Phase 1B",
        "task": "readable_transcript",
        "output_language": output_language,
        "chunk_id": chunk.chunk_id,
        "chunk_start": chunk.start,
        "chunk_end": chunk.end,
        "source_lines": list(chunk.source_lines),
        "session_metadata": session_metadata or {},
    }
    source_lines = ", ".join(str(line) for line in chunk.source_lines) or "none"
    user_prompt = f"""Task: produce Chinese readable transcript segments as structured JSON/state.
Schema fields should include: segments[] with segment_id, start, end, source_text, text_zh, annotations, evidence, status.
Required constraints:
- Chinese readable transcript.
- use only clean transcript evidence.
- no hallucination.
- timestamp grounding.
- structured JSON/state output.
- state JSON is the true source.
- Markdown / HTML are derived by the local renderer.
- mark uncertain content as unclear or suspicious.
- possible correction only for ASR uncertainty.
- do not overwrite clean.txt.
- do not directly generate full Markdown or HTML.

Chunk id: {chunk.chunk_id}
Chunk time range: {chunk.start} -> {chunk.end}
Source line indexes: {source_lines}
Clean transcript chunk:
{chunk.text}
"""
    return PromptPayload(
        system_prompt=PHASE1B_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        metadata=metadata,
    )
