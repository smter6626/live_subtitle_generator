from dataclasses import dataclass
from pathlib import Path

from llm.output_writer import (
    LLMOutputPaths,
    append_markdown_log,
    ensure_llm_dir,
    sanitize_text,
    write_markdown_sidecar_outputs,
)
from llm.prompt_templates import build_markdown_sidecar_payload
from llm.provider_base import LLMProvider
from llm.transcript_chunker import chunk_transcript, parse_clean_transcript


@dataclass(frozen=True)
class MarkdownPipelineResult:
    """Status returned by the Markdown-only LLM sidecar pipeline."""

    success: bool
    chunks_processed: int
    error: str | None
    output_path: Path | None
    log_path: Path | None
    output_paths: LLMOutputPaths | None = None


def run_markdown_pipeline(
    *,
    session_dir: Path,
    provider: LLMProvider,
    max_chars: int = 12000,
    max_seconds: float | None = None,
) -> MarkdownPipelineResult:
    """Run the Markdown-only sidecar pipeline for a completed session."""

    session_path = Path(session_dir)
    paths = ensure_llm_dir(session_path)
    chunks_processed = 0

    try:
        clean_text = (session_path / "clean.txt").read_text(encoding="utf-8")
        lines = parse_clean_transcript(clean_text)
        chunks = chunk_transcript(lines, max_chars=max_chars, max_seconds=max_seconds)

        markdown = _build_markdown_output(chunks=chunks, provider=provider)
        chunks_processed = len(chunks)
        _validate_markdown(markdown)

        output_paths = write_markdown_sidecar_outputs(
            session_path,
            markdown,
            log_message="Markdown sidecar completed.",
            log_details=f"chunks={chunks_processed}",
        )
        return MarkdownPipelineResult(
            success=True,
            chunks_processed=chunks_processed,
            error=None,
            output_path=output_paths.markdown_readable_md,
            log_path=output_paths.markdown_log_md,
            output_paths=output_paths,
        )
    except Exception as exc:
        safe_error = sanitize_text(str(exc))
        append_markdown_log(
            paths.markdown_log_md,
            category=exc.__class__.__name__,
            message="Markdown sidecar failed.",
            details=safe_error,
            llm_dir=paths.llm_dir,
        )
        return MarkdownPipelineResult(
            success=False,
            chunks_processed=chunks_processed,
            error=safe_error,
            output_path=paths.markdown_readable_md if paths.markdown_readable_md.exists() else None,
            log_path=paths.markdown_log_md,
            output_paths=paths,
        )


def _build_markdown_output(*, chunks, provider: LLMProvider) -> str:
    if not chunks:
        return "# 中文课堂阅读稿\n\nclean.txt 没有可处理的内容。\n"

    parts = ["# 中文课堂阅读稿", ""]
    for chunk in chunks:
        payload = build_markdown_sidecar_payload(chunk=chunk)
        markdown = provider.generate_text(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
        )
        if not isinstance(markdown, str):
            raise TypeError("Provider Markdown response must be text.")
        cleaned = sanitize_text(markdown).strip()
        if not cleaned:
            raise ValueError("Provider Markdown response is empty.")
        parts.extend(
            [
                f"## {chunk.chunk_id}",
                "",
                cleaned,
                "",
            ]
        )

    return "\n".join(parts).rstrip() + "\n"


def _validate_markdown(markdown: str):
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("Markdown output is empty.")
