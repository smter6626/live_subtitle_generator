#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Any

from llm.llm_settings import LLMSettings
from llm.output_writer import sanitize_text
from llm.readable_pipeline import run_readable_pipeline
from llm.summary_pipeline import run_summary_pipeline


TASK_SUMMARY = "summary"
TASK_READABLE = "readable"
TASK_BOTH = "both"
SUPPORTED_PROVIDER = "mock"


class CLIMockProvider:
    """Schema-aware deterministic mock provider for offline CLI smoke runs."""

    provider_id = SUPPORTED_PROVIDER

    def __init__(self, *, fail_with: str | None = None, fail_schema: str | None = None):
        self.fail_with = fail_with
        self.fail_schema = fail_schema

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str) -> dict[str, Any]:
        if self.fail_with and (self.fail_schema is None or self.fail_schema == schema_name):
            raise RuntimeError(self.fail_with)

        if schema_name == "phase1a_section_summary":
            return {
                "title": "Mock 阶段",
                "summary": "Mock 总结：本段根据 clean transcript 生成。",
                "key_terms": [
                    {
                        "term": "mock provider",
                        "explanation": "用于离线验证 CLI 和 pipeline 的确定性 provider。",
                        "evidence": ["mock evidence"],
                    }
                ],
                "action_items": [
                    {
                        "text": "检查 mock postprocess 输出",
                        "due": None,
                        "evidence": ["mock evidence"],
                    }
                ],
                "unclear_parts": [],
            }

        if schema_name == "phase1a_global_summary":
            return {
                "overview": "Mock 全局总结：Phase 1A summary pipeline 已跑通。",
                "review_questions": ["如何确认 clean.txt 没有被修改？"],
                "key_terms": [],
                "action_items": [],
                "unclear_parts": [],
            }

        if schema_name == "phase1b_readable_chunk":
            return {
                "segments": [
                    {
                        "start": None,
                        "end": None,
                        "source_text": "mock clean transcript chunk",
                        "text_zh": "Mock 中文阅读稿：本段根据 clean transcript 生成。",
                        "annotations": [],
                        "evidence": ["mock evidence"],
                        "status": "editable",
                    }
                ]
            }

        raise RuntimeError(f"Unsupported mock schema: {schema_name}")

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        if self.fail_with and self.fail_schema is None:
            raise RuntimeError(self.fail_with)
        return "Mock text response."


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    session_dir = Path(args.session)

    if args.provider != SUPPORTED_PROVIDER:
        _print_error("Step 9 only supports mock provider.")
        return 2

    if not session_dir.exists() or not session_dir.is_dir():
        _print_error(f"Session directory does not exist: {session_dir}")
        return 2

    clean_path = session_dir / "clean.txt"
    if not clean_path.exists() or not clean_path.is_file():
        _print_error(f"Missing clean transcript: {clean_path}")
        return 2

    provider = CLIMockProvider(fail_with=args.mock_fail, fail_schema=args.mock_fail_schema)
    settings = LLMSettings(provider=SUPPORTED_PROVIDER, output_language=args.output_language)

    print(f"LLM postprocess: session={session_dir}")
    print(f"Provider: {SUPPORTED_PROVIDER}")
    print(f"Task: {args.task}")

    exit_code = 0
    if args.task in {TASK_SUMMARY, TASK_BOTH}:
        summary_result = run_summary_pipeline(
            session_dir=session_dir,
            provider=provider,
            settings=settings,
            max_chars=args.max_chars,
            max_seconds=args.max_seconds,
        )
        if summary_result.success:
            print(f"summary: ok chunks={summary_result.chunks_processed}")
            _print_paths(
                [
                    summary_result.output_paths.summary_md,
                    summary_result.output_paths.summary_json,
                    summary_result.output_paths.sections_json,
                    summary_result.output_paths.key_terms_json,
                    summary_result.output_paths.action_items_json,
                ]
            )
        else:
            exit_code = 1
            _print_error(f"summary failed: {summary_result.error}")

    if args.task in {TASK_READABLE, TASK_BOTH}:
        readable_result = run_readable_pipeline(
            session_dir=session_dir,
            provider=provider,
            settings=settings,
            max_chars=args.max_chars,
            max_seconds=args.max_seconds,
        )
        if readable_result.success:
            print(f"readable: ok chunks={readable_result.chunks_processed}")
            _print_paths(
                [
                    readable_result.output_paths.readable_state_json,
                    readable_result.output_paths.readable_md,
                    readable_result.output_paths.readable_html,
                    readable_result.output_paths.review_md,
                    readable_result.output_paths.review_html,
                ]
            )
        else:
            exit_code = 1
            _print_error(f"readable failed: {readable_result.error}")

    return exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run mock LLM post-processing for a completed transcript session.",
    )
    parser.add_argument("--session", required=True, help="Completed session directory containing clean.txt.")
    parser.add_argument("--provider", default=SUPPORTED_PROVIDER, help="Provider id. Step 9 supports only mock.")
    parser.add_argument("--task", choices=[TASK_SUMMARY, TASK_READABLE, TASK_BOTH], default=TASK_BOTH)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--output-language", default="zh")
    parser.add_argument("--mock-fail", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--mock-fail-schema", default=None, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _print_paths(paths: list[Path]):
    for path in paths:
        print(f"output: {sanitize_text(str(path))}")


def _print_error(message: str):
    print(f"ERROR: {sanitize_text(message)}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
