from dataclasses import dataclass
from pathlib import Path

from llm.llm_settings import LLMSettings
from llm.provider_base import LLMProvider


@dataclass(frozen=True)
class SummaryPipelineResult:
    """Paths produced by a completed Phase 1A summary pipeline."""

    session_dir: Path
    llm_dir: Path
    summary_md: Path


def run_summary_pipeline(
    *,
    session_dir: Path,
    provider: LLMProvider,
    settings: LLMSettings | None = None,
) -> SummaryPipelineResult:
    """Run the Phase 1A after-stop summary pipeline."""

    raise NotImplementedError("Summary pipeline implementation is deferred to Step 7.")
