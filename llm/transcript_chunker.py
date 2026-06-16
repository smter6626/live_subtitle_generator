from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranscriptLine:
    """One parsed clean transcript line."""

    text: str
    start: float | None = None
    end: float | None = None
    source_line: int | None = None


@dataclass(frozen=True)
class TranscriptChunk:
    """A chunk of clean transcript prepared for LLM prompts."""

    chunk_id: str
    lines: tuple[TranscriptLine, ...] = field(default_factory=tuple)
    start: float | None = None
    end: float | None = None


def parse_clean_transcript(text: str) -> list[TranscriptLine]:
    """Parse clean.txt content into transcript line records."""

    raise NotImplementedError("Transcript parsing is deferred to Step 4.")


def chunk_transcript(
    lines: list[TranscriptLine],
    *,
    max_chars: int = 12000,
    max_seconds: float | None = None,
) -> list[TranscriptChunk]:
    """Split parsed transcript lines into deterministic LLM chunks."""

    raise NotImplementedError("Transcript chunking is deferred to Step 4.")
