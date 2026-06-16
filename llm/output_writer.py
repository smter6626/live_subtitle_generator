from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMOutputPaths:
    """Standard derived output paths under session_dir/llm."""

    llm_dir: Path
    summary_md: Path
    summary_json: Path
    sections_json: Path
    key_terms_json: Path
    action_items_json: Path
    llm_errors_log: Path
    readable_state_json: Path
    readable_md: Path
    readable_html: Path
    review_md: Path
    review_html: Path
    readable_errors_log: Path

    @classmethod
    def for_session(cls, session_dir: Path):
        llm_dir = Path(session_dir) / "llm"
        return cls(
            llm_dir=llm_dir,
            summary_md=llm_dir / "summary.md",
            summary_json=llm_dir / "summary.json",
            sections_json=llm_dir / "sections.json",
            key_terms_json=llm_dir / "key_terms.json",
            action_items_json=llm_dir / "action_items.json",
            llm_errors_log=llm_dir / "llm_errors.log",
            readable_state_json=llm_dir / "readable_zh_final_state.json",
            readable_md=llm_dir / "readable_zh_final.md",
            readable_html=llm_dir / "readable_zh_final.html",
            review_md=llm_dir / "review_zh_final.md",
            review_html=llm_dir / "review_zh_final.html",
            readable_errors_log=llm_dir / "readable_zh_errors.log",
        )


def write_summary_outputs(*args, **kwargs):
    """Write Phase 1A summary outputs under session_dir/llm."""

    raise NotImplementedError("Output writing is deferred to a later step.")
