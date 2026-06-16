from dataclasses import dataclass, field
from enum import Enum


class SegmentStatus(str, Enum):
    EDITABLE = "editable"
    FROZEN = "frozen"


class AnnotationType(str, Enum):
    DUPLICATE = "duplicate"
    TERM = "term"
    UNCLEAR = "unclear"
    HIGH_RISK_UNCLEAR = "high_risk_unclear"


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


@dataclass(frozen=True)
class ReadableTranscriptState:
    schema_version: int = 1
    revision: int = 0
    segments: tuple[ReadableSegment, ...] = field(default_factory=tuple)
