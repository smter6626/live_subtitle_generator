from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm.llm_settings import LLMSettings
from llm.output_writer import LLMOutputPaths, append_error_log, ensure_llm_dir, write_phase1b_outputs
from llm.prompt_templates import build_readable_transcript_payload
from llm.provider_base import LLMError, LLMProvider, LLMSchemaError
from llm.renderer import render_markdown_to_html, render_readable_markdown, render_review_markdown
from llm.state_schema import (
    AnnotationType,
    ReadableSegment,
    ReadableTranscriptState,
    SegmentAnnotation,
    SegmentStatus,
    validate_readable_state,
)
from llm.transcript_chunker import TranscriptChunk, chunk_transcript, parse_clean_transcript


@dataclass(frozen=True)
class ReadablePipelineResult:
    """Status returned by the Phase 1B readable transcript pipeline."""

    session_dir: Path
    llm_dir: Path
    readable_state_json: Path
    success: bool = False
    error: str | None = None
    chunks_processed: int = 0
    output_paths: LLMOutputPaths | None = None


def run_readable_pipeline(
    *,
    session_dir: Path,
    provider: LLMProvider,
    settings: LLMSettings | None = None,
    max_chars: int = 12000,
    max_seconds: float | None = None,
) -> ReadablePipelineResult:
    """Run the Phase 1B after-stop readable transcript mock pipeline."""

    session_path = Path(session_dir)
    paths = ensure_llm_dir(session_path)
    active_settings = settings or LLMSettings()
    chunks_processed = 0

    try:
        clean_path = session_path / "clean.txt"
        clean_text = clean_path.read_text(encoding="utf-8")
        lines = parse_clean_transcript(clean_text)
        chunks = chunk_transcript(lines, max_chars=max_chars, max_seconds=max_seconds)

        state = _build_readable_state(
            chunks=chunks,
            provider=provider,
            output_language=active_settings.output_language,
        )
        chunks_processed = len(chunks)
        validate_readable_state(state)

        readable_markdown = render_readable_markdown(state)
        review_markdown = render_review_markdown(state)
        readable_html = render_markdown_to_html(readable_markdown)
        review_html = render_markdown_to_html(review_markdown)
        output_paths = write_phase1b_outputs(
            session_path,
            state,
            readable_markdown=readable_markdown,
            readable_html=readable_html,
            review_markdown=review_markdown,
            review_html=review_html,
        )

        return ReadablePipelineResult(
            session_dir=session_path,
            llm_dir=paths.llm_dir,
            readable_state_json=output_paths.readable_state_json,
            success=True,
            chunks_processed=chunks_processed,
            output_paths=output_paths,
        )
    except Exception as exc:
        append_error_log(
            paths.readable_errors_log,
            category=exc.__class__.__name__,
            message=str(exc),
            details=_safe_error_details(exc),
            llm_dir=paths.llm_dir,
        )
        return ReadablePipelineResult(
            session_dir=session_path,
            llm_dir=paths.llm_dir,
            readable_state_json=paths.readable_state_json,
            success=False,
            error=str(exc),
            chunks_processed=chunks_processed,
            output_paths=paths,
        )


def _build_readable_state(
    *,
    chunks: list[TranscriptChunk],
    provider: LLMProvider,
    output_language: str,
) -> ReadableTranscriptState:
    if not chunks:
        return ReadableTranscriptState(revision=1, segments=())

    segments: list[ReadableSegment] = []
    for chunk in chunks:
        payload = build_readable_transcript_payload(
            chunk=chunk,
            output_language=output_language,
        )
        response = provider.generate_json(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            schema_name="phase1b_readable_chunk",
        )
        _require_mapping(response, "Readable provider response")
        segments.extend(_normalize_segments(chunk, response))

    return ReadableTranscriptState(revision=1, segments=tuple(segments))


def _normalize_segments(chunk: TranscriptChunk, response: dict[str, Any]) -> list[ReadableSegment]:
    items = response.get("segments")
    if items is None:
        text = (
            _optional_string(response, "text_zh")
            or _optional_string(response, "readable_text")
            or _optional_string(response, "summary")
        )
        if not text:
            raise LLMSchemaError("Readable response must include segments or readable text.")
        items = [
            {
                "segment_id": f"{chunk.chunk_id}-seg-0001",
                "start": chunk.start,
                "end": chunk.end,
                "source_text": chunk.text,
                "text_zh": text,
                "annotations": [],
                "evidence": [_chunk_evidence(chunk)],
                "status": SegmentStatus.EDITABLE.value,
            }
        ]

    if not isinstance(items, list):
        raise LLMSchemaError("segments must be a list.")

    normalized: list[ReadableSegment] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise LLMSchemaError("segments items must be mappings.")

        text_zh = _optional_string(item, "text_zh")
        if not text_zh:
            raise LLMSchemaError("readable segment must include a string text_zh.")

        status_text = _optional_string(item, "status") or SegmentStatus.EDITABLE.value
        try:
            status = SegmentStatus(status_text)
        except ValueError as exc:
            raise LLMSchemaError(f"Invalid segment status: {status_text}") from exc

        normalized.append(
            ReadableSegment(
                segment_id=_optional_string(item, "segment_id") or f"{chunk.chunk_id}-seg-{index:04d}",
                start=_optional_number(item, "start", default=chunk.start),
                end=_optional_number(item, "end", default=chunk.end),
                source_text=_optional_string(item, "source_text") or chunk.text,
                text_zh=text_zh,
                annotations=tuple(_normalize_annotations(item.get("annotations", []))),
                evidence=tuple(_normalize_string_list(item.get("evidence", [_chunk_evidence(chunk)]))),
                status=status,
            )
        )

    return normalized


def _normalize_annotations(items: Any) -> list[SegmentAnnotation]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise LLMSchemaError("annotations must be a list.")

    normalized: list[SegmentAnnotation] = []
    for item in items:
        if isinstance(item, str):
            annotation_type = AnnotationType.UNCLEAR
            text = item
        elif isinstance(item, dict):
            type_text = item.get("annotation_type", item.get("type"))
            if not isinstance(type_text, str):
                raise LLMSchemaError("annotation must include a string annotation_type.")
            try:
                annotation_type = AnnotationType(type_text)
            except ValueError as exc:
                raise LLMSchemaError(f"Invalid annotation type: {type_text}") from exc
            text = _optional_string(item, "text")
        else:
            raise LLMSchemaError("annotation items must be strings or mappings.")

        normalized.append(SegmentAnnotation(annotation_type=annotation_type, text=text))
    return normalized


def _normalize_string_list(items: Any) -> list[str]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise LLMSchemaError("Expected a list of strings.")
    if not all(isinstance(item, str) for item in items):
        raise LLMSchemaError("Expected a list of strings.")
    return list(items)


def _optional_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise LLMSchemaError(f"{key} must be a string.")
    return value


def _optional_number(mapping: dict[str, Any], key: str, *, default: float | None = None) -> float | None:
    value = mapping.get(key, default)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise LLMSchemaError(f"{key} must be a number or null.")
    return float(value)


def _require_mapping(value: Any, label: str):
    if not isinstance(value, dict):
        raise LLMSchemaError(f"{label} must be a mapping.")


def _chunk_evidence(chunk: TranscriptChunk) -> str:
    source_lines = ",".join(str(line) for line in chunk.source_lines) or "none"
    return f"{chunk.chunk_id} {chunk.start}->{chunk.end} source_lines={source_lines}"


def _safe_error_details(exc: Exception) -> str:
    if isinstance(exc, LLMError):
        return f"{exc.__class__.__name__}: {exc}"
    return f"{exc.__class__.__name__}: {exc}"
