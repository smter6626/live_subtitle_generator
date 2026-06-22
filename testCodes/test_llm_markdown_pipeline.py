import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.markdown_pipeline import run_markdown_pipeline  # noqa: E402
from llm.mock_provider import MockProvider  # noqa: E402
from llm.provider_base import LLMProviderError  # noqa: E402


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


class RecordingMarkdownProvider:
    provider_id = "recording_markdown"

    def __init__(self, text="### 课堂片段\n\n- 这是中文 Markdown 输出。"):
        self.text = text
        self.text_calls = []
        self.json_calls = []

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        self.text_calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        return self.text

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        self.json_calls.append(schema_name)
        raise AssertionError("Markdown-only pipeline must not call generate_json().")


class FailingMarkdownProvider:
    provider_id = "failing_markdown"

    def __init__(self, error_text="provider failed"):
        self.error_text = error_text

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        raise LLMProviderError(self.error_text)

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        raise AssertionError("Markdown-only pipeline must not call generate_json().")


def make_fake_secret():
    return "sk-" + ("f" * 24)


def make_session(tmp_path: Path, *, include_clean: bool = True):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    files = {
        "raw.txt": "raw evidence should not change",
        "session.log": "session log",
        "config.json": '{"config": true}',
    }
    if include_clean:
        files["clean.txt"] = "[1s -> 2s] project instructions\n[2s -> 3s] review rubric"

    for name, content in files.items():
        (session_dir / name).write_text(content, encoding="utf-8")
    return session_dir, files


def assert_evidence_unchanged(session_dir: Path, originals: dict[str, str]):
    for name, content in originals.items():
        assert (session_dir / name).read_text(encoding="utf-8") == content


def read_all_outputs(llm_dir: Path):
    content = ""
    if not llm_dir.exists():
        return content
    for path in sorted(llm_dir.glob("*")):
        if path.is_file():
            content += path.read_text(encoding="utf-8")
    return content


def assert_no_structured_outputs(session_dir: Path):
    forbidden = [
        "summary.md",
        "summary.json",
        "sections.json",
        "key_terms.json",
        "action_items.json",
        "llm_errors.log",
        "readable_zh_final_state.json",
        "readable_zh_final.md",
        "readable_zh_final.html",
        "review_zh_final.md",
        "review_zh_final.html",
        "readable_zh_errors.log",
        "live_readable_zh_state.json",
        "live_readable_zh_revisions.jsonl",
        "live_readable_zh.md",
        "live_readable_zh.html",
        "live_review_zh.md",
        "live_review_zh.html",
        "live_readable_zh_errors.log",
    ]
    llm_dir = session_dir / "llm"
    assert not any((llm_dir / name).exists() for name in forbidden)


def test_markdown_pipeline_mock_success():
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_markdown_pipeline(session_dir=session_dir, provider=MockProvider())

        assert result.success
        assert result.chunks_processed == 1
        assert (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm" / "log.md").exists()
        assert "Mock LLM text response." in (session_dir / "llm" / "readable_zh.md").read_text(encoding="utf-8")
        assert_evidence_unchanged(session_dir, originals)
        assert_no_structured_outputs(session_dir)

    print_status("PASS", "markdown pipeline mock text success")


def test_markdown_pipeline_uses_generate_text_only():
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        provider = RecordingMarkdownProvider()
        result = run_markdown_pipeline(session_dir=session_dir, provider=provider)

        assert result.success
        assert len(provider.text_calls) == 1
        assert provider.json_calls == []
        prompt_text = f"{provider.text_calls[0]['system_prompt']}\n{provider.text_calls[0]['user_prompt']}"
        assert "Markdown only" in prompt_text or "Markdown-only" in prompt_text
        assert "no JSON" in prompt_text
        assert "No hallucination" in prompt_text or "no hallucination" in prompt_text

    print_status("PASS", "markdown pipeline uses generate_text only")


def test_markdown_pipeline_failure_preserves_previous_output():
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        first = run_markdown_pipeline(
            session_dir=session_dir,
            provider=RecordingMarkdownProvider("### Previous\n\n- valid output"),
        )
        assert first.success
        readable_path = session_dir / "llm" / "readable_zh.md"
        previous = readable_path.read_text(encoding="utf-8")

        failure = run_markdown_pipeline(
            session_dir=session_dir,
            provider=FailingMarkdownProvider("provider failed after previous output"),
        )

        assert not failure.success
        assert readable_path.read_text(encoding="utf-8") == previous
        log_text = (session_dir / "llm" / "log.md").read_text(encoding="utf-8")
        assert "Markdown sidecar failed" in log_text
        assert_evidence_unchanged(session_dir, originals)
        assert_no_structured_outputs(session_dir)

    print_status("PASS", "markdown provider failure preserves previous output")


def test_markdown_pipeline_missing_clean_fails():
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), include_clean=False)
        result = run_markdown_pipeline(session_dir=session_dir, provider=RecordingMarkdownProvider())

        assert not result.success
        assert not (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm" / "log.md").exists()
        assert_evidence_unchanged(session_dir, originals)
        assert_no_structured_outputs(session_dir)

    print_status("PASS", "markdown missing clean transcript failure")


def test_markdown_pipeline_secret_safety():
    secret = make_fake_secret()
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        success = run_markdown_pipeline(
            session_dir=session_dir,
            provider=RecordingMarkdownProvider(f"### secret\n\n{secret}"),
        )
        assert success.success
        output = read_all_outputs(session_dir / "llm")
        assert secret not in output

    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        failure = run_markdown_pipeline(
            session_dir=session_dir,
            provider=FailingMarkdownProvider(f"failed {secret}"),
        )
        assert not failure.success
        output = read_all_outputs(session_dir / "llm")
        assert secret not in output

    print_status("PASS", "markdown api key not written")


def test_markdown_pipeline_no_real_api_call():
    with tempfile.TemporaryDirectory(prefix="llm_markdown_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        provider = RecordingMarkdownProvider()
        result = run_markdown_pipeline(session_dir=session_dir, provider=provider)

        assert result.success
        assert len(provider.text_calls) == 1

    print_status("PASS", "markdown no real API call")


def main():
    test_markdown_pipeline_mock_success()
    test_markdown_pipeline_uses_generate_text_only()
    test_markdown_pipeline_failure_preserves_previous_output()
    test_markdown_pipeline_missing_clean_fails()
    test_markdown_pipeline_secret_safety()
    test_markdown_pipeline_no_real_api_call()


if __name__ == "__main__":
    main()
