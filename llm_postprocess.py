#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from llm.markdown_pipeline import run_markdown_pipeline
from llm.output_writer import sanitize_text


TASK_MARKDOWN = "markdown"
SUPPORTED_PROVIDER = "mock"


class CLIMockProvider:
    """Deterministic text mock provider for offline Markdown CLI smoke runs."""

    provider_id = SUPPORTED_PROVIDER

    def __init__(self, *, fail_with: str | None = None):
        self.fail_with = fail_with

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        raise RuntimeError("Markdown-only CLI does not use generate_json.")

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        if self.fail_with:
            raise RuntimeError(self.fail_with)
        return (
            "### Mock 中文阅读稿\n\n"
            "- 基于 clean transcript 生成的 Markdown-only mock 输出。\n"
            "- 这是离线测试内容，不调用真实 API。\n"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    session_dir = Path(args.session)

    if args.provider != SUPPORTED_PROVIDER:
        _print_error("Markdown CLI only supports mock provider.")
        return 2

    if not session_dir.exists() or not session_dir.is_dir():
        _print_error(f"Session directory does not exist: {session_dir}")
        return 2

    clean_path = session_dir / "clean.txt"
    if not clean_path.exists() or not clean_path.is_file():
        _print_error(f"Missing clean transcript: {clean_path}")
        return 2

    provider = CLIMockProvider(fail_with=args.mock_fail)

    print(f"LLM postprocess: session={session_dir}")
    print(f"Provider: {SUPPORTED_PROVIDER}")
    print(f"Task: {args.task}")

    result = run_markdown_pipeline(
        session_dir=session_dir,
        provider=provider,
        max_chars=args.max_chars,
        max_seconds=args.max_seconds,
    )
    if result.success:
        print(f"markdown: ok chunks={result.chunks_processed}")
        _print_paths([result.output_path, result.log_path])
        return 0

    _print_error(f"markdown failed: {result.error}")
    if result.log_path:
        _print_paths([result.log_path])
    return 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Markdown-only mock LLM post-processing for a completed transcript session.",
    )
    parser.add_argument("--session", required=True, help="Completed session directory containing clean.txt.")
    parser.add_argument("--provider", default=SUPPORTED_PROVIDER, help="Provider id. Markdown CLI supports only mock.")
    parser.add_argument("--task", choices=[TASK_MARKDOWN], default=TASK_MARKDOWN)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--mock-fail", default=None, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _print_paths(paths: list[Path | None]):
    for path in paths:
        if path is not None:
            print(f"output: {sanitize_text(str(path))}")


def _print_error(message: str):
    print(f"ERROR: {sanitize_text(message)}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
