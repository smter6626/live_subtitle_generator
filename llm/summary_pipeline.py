from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm.llm_settings import LLMSettings
from llm.output_writer import LLMOutputPaths, append_error_log, ensure_llm_dir, write_phase1a_outputs
from llm.prompt_templates import build_global_summary_payload, build_section_summary_payload
from llm.provider_base import LLMError, LLMProvider, LLMSchemaError
from llm.renderer import render_summary_markdown
from llm.state_schema import (
    ActionItem,
    KeyTerm,
    SectionSummary,
    SummaryState,
    UnclearPart,
    validate_summary_state,
)
from llm.transcript_chunker import TranscriptChunk, chunk_transcript, parse_clean_transcript


@dataclass(frozen=True)
class SummaryPipelineResult:
    """Status returned by the Phase 1A summary pipeline."""

    session_dir: Path
    llm_dir: Path
    summary_md: Path
    success: bool = False
    error: str | None = None
    chunks_processed: int = 0
    output_paths: LLMOutputPaths | None = None


def run_summary_pipeline(
    *,
    session_dir: Path,
    provider: LLMProvider,
    settings: LLMSettings | None = None,
    max_chars: int = 12000,
    max_seconds: float | None = None,
) -> SummaryPipelineResult:
    """Run the Phase 1A after-stop summary mock pipeline."""

    session_path = Path(session_dir)
    paths = ensure_llm_dir(session_path)
    active_settings = settings or LLMSettings()

    try:
        clean_path = session_path / "clean.txt"
        clean_text = clean_path.read_text(encoding="utf-8")
        lines = parse_clean_transcript(clean_text)
        chunks = chunk_transcript(lines, max_chars=max_chars, max_seconds=max_seconds)

        state = _build_summary_state(
            chunks=chunks,
            provider=provider,
            output_language=active_settings.output_language,
        )
        validate_summary_state(state)
        summary_markdown = render_summary_markdown(state)
        output_paths = write_phase1a_outputs(session_path, state, summary_markdown)

        return SummaryPipelineResult(
            session_dir=session_path,
            llm_dir=paths.llm_dir,
            summary_md=output_paths.summary_md,
            success=True,
            chunks_processed=len(chunks),
            output_paths=output_paths,
        )
    except Exception as exc:
        append_error_log(
            paths.llm_errors_log,
            category=exc.__class__.__name__,
            message=str(exc),
            details=_safe_error_details(exc),
            llm_dir=paths.llm_dir,
        )
        return SummaryPipelineResult(
            session_dir=session_path,
            llm_dir=paths.llm_dir,
            summary_md=paths.summary_md,
            success=False,
            error=str(exc),
            chunks_processed=0,
            output_paths=paths,
        )


def _build_summary_state(
    *,
    chunks: list[TranscriptChunk],
    provider: LLMProvider,
    output_language: str,
) -> SummaryState:
    if not chunks:
        return SummaryState(
            overview="clean.txt 没有可总结的内容。",
            review_questions=(),
        )

    sections: list[SectionSummary] = []
    key_terms: list[KeyTerm] = []
    action_items: list[ActionItem] = []
    unclear_parts: list[UnclearPart] = []

    for index, chunk in enumerate(chunks, start=1):
        payload = build_section_summary_payload(
            chunk=chunk,
            output_language=output_language,
        )
        response = provider.generate_json(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            schema_name="phase1a_section_summary",
        )
        _require_mapping(response, "Section provider response")
        sections.append(_normalize_section(index, chunk, response))
        key_terms.extend(_normalize_key_terms(response.get("key_terms", [])))
        action_items.extend(_normalize_action_items(response.get("action_items", [])))
        unclear_parts.extend(_normalize_unclear_parts(response.get("unclear_parts", [])))

    global_payload = build_global_summary_payload(
        section_summaries="\n".join(section.summary for section in sections),
        output_language=output_language,
    )
    global_response = provider.generate_json(
        system_prompt=global_payload.system_prompt,
        user_prompt=global_payload.user_prompt,
        schema_name="phase1a_global_summary",
    )
    _require_mapping(global_response, "Global provider response")

    key_terms.extend(_normalize_key_terms(global_response.get("key_terms", [])))
    action_items.extend(_normalize_action_items(global_response.get("action_items", [])))
    unclear_parts.extend(_normalize_unclear_parts(global_response.get("unclear_parts", [])))
    review_questions = tuple(_normalize_string_list(global_response.get("review_questions", [])))

    overview = _optional_string(global_response, "overview")
    if not overview:
        overview = _optional_string(global_response, "summary")
    if not overview:
        overview = "\n".join(section.summary for section in sections)

    return SummaryState(
        overview=overview,
        sections=tuple(sections),
        key_terms=tuple(key_terms),
        action_items=tuple(action_items),
        review_questions=review_questions,
        unclear_parts=tuple(unclear_parts),
    )


def _normalize_section(index: int, chunk: TranscriptChunk, response: dict[str, Any]) -> SectionSummary:
    title = _optional_string(response, "title") or f"阶段 {index}"
    summary = _optional_string(response, "summary")
    if not summary:
        raise LLMSchemaError("Section response must include a string summary.")

    return SectionSummary(
        section_id=chunk.chunk_id,
        title=title,
        summary=summary,
        start=chunk.start,
        end=chunk.end,
        evidence=(_chunk_evidence(chunk),),
    )


def _normalize_key_terms(items: Any) -> list[KeyTerm]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise LLMSchemaError("key_terms must be a list.")

    normalized: list[KeyTerm] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(KeyTerm(term=item, explanation=""))
        elif isinstance(item, dict):
            term = _optional_string(item, "term")
            if not term:
                raise LLMSchemaError("key term item must include a string term.")
            normalized.append(
                KeyTerm(
                    term=term,
                    explanation=_optional_string(item, "explanation"),
                    evidence=tuple(_normalize_string_list(item.get("evidence", []))),
                )
            )
        else:
            raise LLMSchemaError("key_terms items must be strings or mappings.")
    return normalized


def _normalize_action_items(items: Any) -> list[ActionItem]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise LLMSchemaError("action_items must be a list.")

    normalized: list[ActionItem] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(ActionItem(text=item))
        elif isinstance(item, dict):
            text = _optional_string(item, "text")
            if not text:
                raise LLMSchemaError("action item must include a string text.")
            normalized.append(
                ActionItem(
                    text=text,
                    owner=_optional_nullable_string(item, "owner"),
                    due=_optional_nullable_string(item, "due"),
                    evidence=tuple(_normalize_string_list(item.get("evidence", []))),
                )
            )
        else:
            raise LLMSchemaError("action_items items must be strings or mappings.")
    return normalized


def _normalize_unclear_parts(items: Any) -> list[UnclearPart]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise LLMSchemaError("unclear_parts must be a list.")

    normalized: list[UnclearPart] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(UnclearPart(text=item, reason="unclear"))
        elif isinstance(item, dict):
            text = _optional_string(item, "text")
            if not text:
                raise LLMSchemaError("unclear part must include a string text.")
            normalized.append(
                UnclearPart(
                    text=text,
                    reason=_optional_string(item, "reason"),
                    possible_correction=_optional_nullable_string(item, "possible_correction"),
                    evidence=tuple(_normalize_string_list(item.get("evidence", []))),
                )
            )
        else:
            raise LLMSchemaError("unclear_parts items must be strings or mappings.")
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


def _optional_nullable_string(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise LLMSchemaError(f"{key} must be a string or null.")
    return value


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
