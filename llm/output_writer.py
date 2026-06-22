import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm.state_schema import (
    validate_readable_state,
    validate_summary_state,
)


_SECRET_PATTERNS = [
    re.compile(r"sk-" + r"[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)" + "bear" + r"er\s+[A-Za-z0-9._-]+"),
    re.compile(r"(?i)" + "author" + r"ization\s*:\s*[^\s,;]+"),
    re.compile(r"(?i)DEEPSEEK_API_KEY\s*=\s*[^\s,;]+"),
]
_REDACTION = "[REDACTED]"
_MAX_ERROR_DETAIL_CHARS = 500


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


def ensure_llm_dir(session_dir: Path) -> LLMOutputPaths:
    """Create session_dir/llm and return standard output paths."""

    paths = LLMOutputPaths.for_session(Path(session_dir))
    paths.llm_dir.mkdir(parents=True, exist_ok=True)
    return paths


def atomic_write_text(path: Path, text: str, *, llm_dir: Path):
    """Atomically write text to a path under llm_dir."""

    target = _validate_output_path(path, llm_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_text = sanitize_text(text)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(safe_text)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_json(path: Path, data: Any, *, llm_dir: Path):
    """Atomically write sanitized JSON to a path under llm_dir."""

    json_text = json.dumps(sanitize_data(data), ensure_ascii=False, indent=2, sort_keys=True)
    atomic_write_text(path, f"{json_text}\n", llm_dir=llm_dir)


def append_error_log(
    path: Path,
    *,
    category: str,
    message: str,
    details: Any | None = None,
    llm_dir: Path,
):
    """Append a sanitized diagnostic line to an LLM-owned error log."""

    target = _validate_output_path(path, llm_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    safe_category = sanitize_text(category)
    safe_message = sanitize_text(message)
    line = f"{timestamp}\t{safe_category}\t{safe_message}"
    if details is not None:
        safe_details = sanitize_text(str(details))[:_MAX_ERROR_DETAIL_CHARS]
        line = f"{line}\t{safe_details}"

    with target.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{line}\n")


def write_phase1a_outputs(session_dir: Path, summary_state: Any, summary_markdown: str) -> LLMOutputPaths:
    """Write Phase 1A summary Markdown and JSON outputs."""

    paths = ensure_llm_dir(session_dir)
    state_data = validate_summary_state(summary_state)
    atomic_write_text(paths.summary_md, summary_markdown, llm_dir=paths.llm_dir)
    atomic_write_json(paths.summary_json, state_data, llm_dir=paths.llm_dir)
    atomic_write_json(paths.sections_json, state_data["sections"], llm_dir=paths.llm_dir)
    atomic_write_json(paths.key_terms_json, state_data["key_terms"], llm_dir=paths.llm_dir)
    atomic_write_json(paths.action_items_json, state_data["action_items"], llm_dir=paths.llm_dir)
    return paths


def write_phase1b_outputs(
    session_dir: Path,
    readable_state: Any,
    *,
    readable_markdown: str,
    readable_html: str,
    review_markdown: str,
    review_html: str,
) -> LLMOutputPaths:
    """Write Phase 1B readable/review state and derived views."""

    paths = ensure_llm_dir(session_dir)
    state_data = validate_readable_state(readable_state)
    atomic_write_json(paths.readable_state_json, state_data, llm_dir=paths.llm_dir)
    atomic_write_text(paths.readable_md, readable_markdown, llm_dir=paths.llm_dir)
    atomic_write_text(paths.readable_html, readable_html, llm_dir=paths.llm_dir)
    atomic_write_text(paths.review_md, review_markdown, llm_dir=paths.llm_dir)
    atomic_write_text(paths.review_html, review_html, llm_dir=paths.llm_dir)
    return paths


def sanitize_text(text: str) -> str:
    """Redact obvious secret shapes from text before persisting it."""

    safe = str(text)
    for pattern in _SECRET_PATTERNS:
        safe = pattern.sub(_REDACTION, safe)
    return safe


def sanitize_data(data: Any) -> Any:
    """Recursively redact strings in JSON-compatible structures."""

    if isinstance(data, str):
        return sanitize_text(data)
    if isinstance(data, list):
        return [sanitize_data(item) for item in data]
    if isinstance(data, tuple):
        return [sanitize_data(item) for item in data]
    if isinstance(data, dict):
        return {str(key): sanitize_data(value) for key, value in data.items()}
    return data


def _validate_output_path(path: Path, llm_dir: Path) -> Path:
    target = Path(path)
    root = Path(llm_dir)
    resolved_target = target.resolve(strict=False)
    resolved_root = root.resolve(strict=False)

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"LLM output path must be under {resolved_root}") from exc

    return target
