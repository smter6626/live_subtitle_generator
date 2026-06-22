from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from llm.provider_base import LLMSchemaError


class SegmentStatus(str, Enum):
    EDITABLE = "editable"
    FROZEN = "frozen"


class AnnotationType(str, Enum):
    DUPLICATE = "duplicate"
    SUSPECTED_DUPLICATE = "suspected_duplicate"
    DELETION = "deletion"
    TERM = "term"
    UNCERTAIN_TRANSLATION = "uncertain_translation"
    UNCLEAR = "unclear"
    SUSPICIOUS = "suspicious"
    HIGH_RISK_UNCLEAR = "high_risk_unclear"
    HIGH_RISK_SUSPICIOUS = "high_risk_suspicious"


@dataclass(frozen=True)
class SourceInfo:
    transcript: str = "clean.txt"
    raw_used: bool = False


@dataclass(frozen=True)
class SectionSummary:
    section_id: str
    title: str
    summary: str
    start: float | None = None
    end: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KeyTerm:
    term: str
    explanation: str
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ActionItem:
    text: str
    owner: str | None = None
    due: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UnclearPart:
    text: str
    reason: str = ""
    possible_correction: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SummaryState:
    schema_version: int = 1
    source: SourceInfo = field(default_factory=SourceInfo)
    overview: str = ""
    sections: tuple[SectionSummary, ...] = field(default_factory=tuple)
    key_terms: tuple[KeyTerm, ...] = field(default_factory=tuple)
    action_items: tuple[ActionItem, ...] = field(default_factory=tuple)
    review_questions: tuple[str, ...] = field(default_factory=tuple)
    unclear_parts: tuple[UnclearPart, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SegmentAnnotation:
    annotation_type: AnnotationType
    text: str = ""


@dataclass(frozen=True)
class ReadableSegment:
    segment_id: str
    text_zh: str
    start: float | None = None
    end: float | None = None
    source_text: str = ""
    status: SegmentStatus = SegmentStatus.EDITABLE
    annotations: tuple[SegmentAnnotation, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReadableTranscriptState:
    schema_version: int = 1
    revision: int = 0
    source: SourceInfo = field(default_factory=SourceInfo)
    segments: tuple[ReadableSegment, ...] = field(default_factory=tuple)


def state_to_dict(value: Any) -> Any:
    """Convert state dataclasses and enums into JSON-compatible values."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: state_to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): state_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [state_to_dict(item) for item in value]
    return value


def validate_summary_state(state: SummaryState | dict[str, Any]) -> dict[str, Any]:
    """Validate the minimal Phase 1A summary schema."""

    data = state_to_dict(state)
    if not isinstance(data, dict):
        raise LLMSchemaError("Summary state must be a mapping.")

    _require_int(data, "schema_version")
    source = _require_mapping(data, "source")
    _validate_source(source)
    _require_str(data, "overview")
    _require_list(data, "sections")
    _require_list(data, "key_terms")
    _require_list(data, "action_items")
    _require_list(data, "review_questions")
    _require_list(data, "unclear_parts")

    for section in data["sections"]:
        _validate_section(section)
    for term in data["key_terms"]:
        _validate_key_term(term)
    for item in data["action_items"]:
        _validate_action_item(item)
    for question in data["review_questions"]:
        if not isinstance(question, str):
            raise LLMSchemaError("Review questions must be strings.")
    for unclear in data["unclear_parts"]:
        _validate_unclear_part(unclear)

    return data


def validate_readable_state(state: ReadableTranscriptState | dict[str, Any]) -> dict[str, Any]:
    """Validate the minimal Phase 1B readable transcript schema."""

    data = state_to_dict(state)
    if not isinstance(data, dict):
        raise LLMSchemaError("Readable transcript state must be a mapping.")

    _require_int(data, "schema_version")
    _require_int(data, "revision")
    source = _require_mapping(data, "source")
    _validate_source(source)
    segments = _require_list(data, "segments")

    for segment in segments:
        _validate_segment(segment)

    return data


def _validate_source(source: dict[str, Any]):
    transcript = source.get("transcript")
    raw_used = source.get("raw_used")
    if transcript != "clean.txt":
        raise LLMSchemaError("State source.transcript must be clean.txt.")
    if raw_used is not False:
        raise LLMSchemaError("State source.raw_used must be false for Phase 1.")


def _validate_section(section: Any):
    mapping = _expect_mapping(section, "Section")
    _require_str(mapping, "section_id")
    _require_str(mapping, "title")
    _require_str(mapping, "summary")
    _require_optional_number(mapping, "start")
    _require_optional_number(mapping, "end")
    _require_string_list(mapping, "evidence")


def _validate_key_term(term: Any):
    mapping = _expect_mapping(term, "Key term")
    _require_str(mapping, "term")
    _require_str(mapping, "explanation")
    _require_string_list(mapping, "evidence")


def _validate_action_item(item: Any):
    mapping = _expect_mapping(item, "Action item")
    _require_str(mapping, "text")
    _require_optional_str(mapping, "owner")
    _require_optional_str(mapping, "due")
    _require_string_list(mapping, "evidence")


def _validate_unclear_part(unclear: Any):
    mapping = _expect_mapping(unclear, "Unclear part")
    _require_str(mapping, "text")
    _require_str(mapping, "reason")
    _require_optional_str(mapping, "possible_correction")
    _require_string_list(mapping, "evidence")


def _validate_segment(segment: Any):
    mapping = _expect_mapping(segment, "Readable segment")
    _require_str(mapping, "segment_id")
    _require_optional_number(mapping, "start")
    _require_optional_number(mapping, "end")
    _require_str(mapping, "source_text")
    _require_str(mapping, "text_zh")
    _require_string_list(mapping, "evidence")

    status = _require_str(mapping, "status")
    if status not in {item.value for item in SegmentStatus}:
        raise LLMSchemaError(f"Invalid segment status: {status}")

    annotations = _require_list(mapping, "annotations")
    for annotation in annotations:
        _validate_annotation(annotation)


def _validate_annotation(annotation: Any):
    mapping = _expect_mapping(annotation, "Annotation")
    annotation_type = mapping.get("annotation_type", mapping.get("type"))
    if annotation_type not in {item.value for item in AnnotationType}:
        raise LLMSchemaError(f"Invalid annotation type: {annotation_type}")
    _require_str({"text": mapping.get("text", "")}, "text")


def _expect_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LLMSchemaError(f"{label} must be a mapping.")
    return value


def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise LLMSchemaError(f"{key} must be a mapping.")
    return value


def _require_list(mapping: dict[str, Any], key: str) -> list[Any]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise LLMSchemaError(f"{key} must be a list.")
    return value


def _require_string_list(mapping: dict[str, Any], key: str):
    value = _require_list(mapping, key)
    if not all(isinstance(item, str) for item in value):
        raise LLMSchemaError(f"{key} must contain only strings.")


def _require_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise LLMSchemaError(f"{key} must be an integer.")
    return value


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise LLMSchemaError(f"{key} must be a string.")
    return value


def _require_optional_str(mapping: dict[str, Any], key: str):
    value = mapping.get(key)
    if value is not None and not isinstance(value, str):
        raise LLMSchemaError(f"{key} must be a string or null.")


def _require_optional_number(mapping: dict[str, Any], key: str):
    value = mapping.get(key)
    if value is not None and not isinstance(value, (int, float)):
        raise LLMSchemaError(f"{key} must be a number or null.")
