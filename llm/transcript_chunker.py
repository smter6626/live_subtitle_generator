import re
from dataclasses import dataclass, field


_TIMESTAMP_PREFIX_RE = re.compile(
    r"^\[(?P<start>\d+(?:\.\d+)?)s\s*->\s*(?P<end>\d+(?:\.\d+)?)s\]\s*(?P<text>.*)$"
)


@dataclass(frozen=True)
class TranscriptLine:
    """One parsed clean transcript line."""

    text: str
    start: float | None = None
    end: float | None = None
    source_line: int | None = None
    raw_line: str | None = None


@dataclass(frozen=True)
class TranscriptChunk:
    """A chunk of clean transcript prepared for LLM prompts."""

    chunk_id: str
    lines: tuple[TranscriptLine, ...] = field(default_factory=tuple)
    start: float | None = None
    end: float | None = None

    @property
    def text(self) -> str:
        """Chunk text assembled from parsed transcript lines."""

        return "\n".join(line.text for line in self.lines)

    @property
    def source_lines(self) -> tuple[int, ...]:
        """Original 0-based source line indexes represented by this chunk."""

        return tuple(line.source_line for line in self.lines if line.source_line is not None)


def parse_clean_transcript(text: str) -> list[TranscriptLine]:
    """Parse clean.txt content into transcript line records."""

    parsed: list[TranscriptLine] = []
    for source_line, raw_line in enumerate(text.splitlines()):
        if not raw_line.strip():
            continue

        match = _TIMESTAMP_PREFIX_RE.match(raw_line)
        if not match:
            parsed.append(
                TranscriptLine(text=raw_line, source_line=source_line, raw_line=raw_line)
            )
            continue

        start = float(match.group("start"))
        end = float(match.group("end"))
        if end < start:
            parsed.append(
                TranscriptLine(text=raw_line, source_line=source_line, raw_line=raw_line)
            )
            continue

        parsed.append(
            TranscriptLine(
                text=match.group("text"),
                start=start,
                end=end,
                source_line=source_line,
                raw_line=raw_line,
            )
        )

    return parsed


def chunk_transcript(
    lines: list[TranscriptLine],
    *,
    max_chars: int = 12000,
    max_seconds: float | None = None,
) -> list[TranscriptChunk]:
    """Split parsed transcript lines into deterministic LLM chunks."""

    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError("max_seconds must be positive when provided.")

    chunks: list[TranscriptChunk] = []
    current: list[TranscriptLine] = []

    for line in lines:
        if current and _would_exceed_limits(
            (*current, line),
            max_chars=max_chars,
            max_seconds=max_seconds,
        ):
            chunks.append(_build_chunk(len(chunks) + 1, current))
            current = []

        current.append(line)

    if current:
        chunks.append(_build_chunk(len(chunks) + 1, current))

    return chunks


def _would_exceed_limits(
    candidate_lines: tuple[TranscriptLine, ...],
    *,
    max_chars: int,
    max_seconds: float | None,
) -> bool:
    text = "\n".join(line.text for line in candidate_lines)
    if len(text) > max_chars:
        return True

    if max_seconds is None:
        return False

    start, end = _chunk_time_bounds(candidate_lines)
    if start is None or end is None:
        return False

    return end - start > max_seconds


def _build_chunk(chunk_number: int, lines: list[TranscriptLine]) -> TranscriptChunk:
    chunk_lines = tuple(lines)
    start, end = _chunk_time_bounds(chunk_lines)
    return TranscriptChunk(
        chunk_id=f"chunk-{chunk_number:04d}",
        lines=chunk_lines,
        start=start,
        end=end,
    )


def _chunk_time_bounds(lines: tuple[TranscriptLine, ...]) -> tuple[float | None, float | None]:
    start: float | None = None
    end: float | None = None

    for line in lines:
        if line.start is not None and start is None:
            start = line.start
        if line.end is not None:
            end = line.end

    if start is None and end is None:
        return None, None
    return start, end
